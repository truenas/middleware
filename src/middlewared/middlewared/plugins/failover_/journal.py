from asyncio import ensure_future
from pickle import dump, load
from os import rename
from errno import ECONNREFUSED, ECONNRESET
from queue import Queue, Empty
from threading import Thread
from logging import getLogger
from contextlib import suppress
from time import sleep
from prctl import set_name

from middlewared.service import CallError, Service
from middlewared.plugins.failover_.journal_exceptions import UnableToDetermineOSVersion, OSVersionMismatch

logger = getLogger(__name__)
SQL_QUEUE = Queue()
JOURNAL_THREAD = None


class JournalSync:
    def __init__(self, middleware, sql_queue, journal):
        self.middleware = middleware
        self.sql_queue = sql_queue
        self.journal = journal
        self.failover_status = None
        self._update_failover_status()

        self.last_query_failed = False  # this only affects logging

    def process(self):
        if self.failover_status != 'MASTER':
            if self.journal:
                logger.warning('Node status %s but has %d queries in journal', self.failover_status, len(self.journal))

            self.journal.clear()

        if self.journal:
            os_ver_match = self._os_versions_match()
            if os_ver_match is None:
                raise UnableToDetermineOSVersion()
            elif not os_ver_match:
                raise OSVersionMismatch()

        had_journal_items = bool(self.journal)
        flush_succeeded = self._flush_journal()

        if had_journal_items:
            # We've spent some flushing journal, failover status might have changed
            self._update_failover_status()

        self._consume_queue_nonblocking()
        self.journal.write()

        # Avoid busy loop
        if flush_succeeded:
            # The other node is synchronized, we can wait until new query arrives
            timeout = None
        else:
            # Retry in N seconds,
            timeout = 5

        try:
            item = self.sql_queue.get(True, timeout)
        except Empty:
            pass
        else:
            # We've spent some time waiting, failover status might have changed
            self._update_failover_status()

            self._handle_sql_queue_item(item)

            # Consume other pending queries
            self._consume_queue_nonblocking()

        self.journal.write()

    def _flush_journal(self):
        while self.journal:
            query, params = self.journal.peek()

            try:
                self.middleware.call_sync('failover.call_remote', 'datastore.sql', [query, params])
            except Exception as e:
                if isinstance(e, CallError) and e.errno in [ECONNREFUSED, ECONNRESET]:
                    logger.trace('Skipping journal sync, node down')
                else:
                    if not self.last_query_failed:
                        logger.exception('Failed to run query %s: %r', query, e)
                        self.last_query_failed = True

                    self.middleware.call_sync('alert.oneshot_create', 'FailoverSyncFailed', None)

                return False
            else:
                self.last_query_failed = False

                self.middleware.call_sync('alert.oneshot_delete', 'FailoverSyncFailed', None)

                self.journal.shift()

        return True

    def _consume_queue_nonblocking(self):
        while True:
            try:
                self._handle_sql_queue_item(self.sql_queue.get_nowait())
            except Empty:
                break

    def _handle_sql_queue_item(self, item):
        if item is None:
            # This is sent by `failover.send_database`
            self.journal.clear()
        else:
            if self.failover_status == 'SINGLE':
                pass
            elif self.failover_status == 'MASTER':
                self.journal.append(item)
            else:
                query, params = item
                logger.warning('Node status %s but executed SQL query: %s', self.failover_status, query)

    def _update_failover_status(self):
        self.failover_status = self.middleware.call_sync('failover.status')

    def _os_versions_match(self):

        try:
            rem = self.middleware.call_sync('failover.get_remote_os_version')
            loc = self.middleware.call_sync('system.version')
        except Exception:
            return False

        if rem is None:
            # happens when other node goes offline
            # (reboot/upgrade etc, etc) the log message
            # is a little misleading in this scenario
            # so make it a little better
            return
        else:
            return loc == rem


class Journal:
    path = '/data/ha-journal'

    def __init__(self):
        self.journal = []
        with suppress(FileNotFoundError):
            with open(self.path, 'rb') as f:
                try:
                    self.journal = load(f)
                except EOFError:
                    # file is empty
                    pass
                except Exception:
                    logger.warning('Failed to read journal', exc_info=True)

        self.persisted_journal = self.journal.copy()

    def __bool__(self):
        return bool(self.journal)

    def __iter__(self):
        for query, params in self.journal:
            yield query, params

    def __len__(self):
        return len(self.journal)

    def peek(self):
        return self.journal[0]

    def shift(self):
        self.journal = self.journal[1:]

    def append(self, item):
        self.journal.append(item)

    def clear(self):
        self.journal = []

    def write(self):
        if self.persisted_journal != self.journal:
            self._write()
            self.persisted_journal = self.journal.copy()

    def _write(self):
        tmp_file = f'{self.path}.tmp'
        with open(tmp_file, 'wb') as f:
            dump(self.journal, f)

        rename(tmp_file, self.path)


class JournalSyncThread(Thread):
    """
    A thread that is responsible for trying to sync the journal file to
    the other node. Every SQL query that could not be synced is stored
    in the journal.
    """
    def __init__(self, *args, **kwargs):
        super(JournalSyncThread, self).__init__()
        self.daemon = True
        self.middleware = kwargs.get('middleware')
        self.sql_queue = kwargs.get('sql_queue')

    def run(self):
        set_name('journal_sync_thread')

        alert = True
        retry_timeout = 5
        while True:
            try:
                journal = Journal()
                journal_sync = JournalSync(self.middleware, self.sql_queue, journal)
                while True:
                    journal_sync.process()
                    alert = True
            except UnableToDetermineOSVersion:
                if alert:
                    logger.warning('Unable to determine remote node OS version. Not syncing journal')
                    alert = False
            except OSVersionMismatch:
                if alert:
                    logger.warning('OS version does not match remote node. Not syncing journal')
                    alert = False
            except Exception:
                logger.warning('Failed to sync journal. Retrying ever %d seconds', retry_timeout, exc_info=True)

            sleep(retry_timeout)


class JournalSyncService(Service):
    THREAD = None

    class Config:
        private = True
        namespace = 'failover.journal'

    def thread_running(self):
        return JournalSyncService.THREAD is not None and JournalSyncService.THREAD.is_alive()

    def setup(self):
        licensed = self.middleware.call_sync('failover.licensed')
        if licensed and (JournalSyncService.THREAD is None or not JournalSyncService.THREAD.is_alive()):
            JournalSyncService.THREAD = JournalSyncThread(middleware=self.middleware, sql_queue=SQL_QUEUE)
            JournalSyncService.THREAD.start()


def hook_datastore_execute_write(middleware, sql, params, options):
    if not options['ha_sync']:
        return

    SQL_QUEUE.put((sql, params))


async def _event_system(middleware, *args, **kwargs):
    await middleware.call('failover.journal.setup')


async def setup(middleware):
    if not await middleware.call('system.is_enterprise'):
        return

    middleware.register_hook('datastore.post_execute_write', hook_datastore_execute_write, inline=True)
    middleware.register_hook('system.post_license_update', _event_system)  # catch license change
    middleware.register_hook('system', _event_system)  # catch middlewared service restart
    ensure_future(_event_system(middleware))  # start thread on middlewared service start/restart
