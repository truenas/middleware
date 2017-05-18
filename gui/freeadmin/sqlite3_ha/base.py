

import logging
import os
import socket
import threading
import time
import xmlrpc.client
from sqlite3 import OperationalError

from django.db.backends.sqlite3 import base as sqlite3base
from lockfile import LockFile, LockTimeout
import pickle as pickle
import sqlparse

Database = sqlite3base.Database
DatabaseError = sqlite3base.DatabaseError
IntegrityError = sqlite3base.IntegrityError

execute_sync = False
log = logging.getLogger('freeadmin.sqlite3_ha')


"""
Mapping of tables to not to replicate to the remote side

It accepts a fields key which will then exclude these fields and not the
whole table.
"""
NO_SYNC_MAP = {
    'system_failover': {
        'fields': ['master'],
    },
}


class DBSync(object):
    """
    Allow to execute all queries made within a with statement
    in a synchronous way.
    This is not thread-safe.
    """

    def __enter__(self):
        global execute_sync
        execute_sync = True

    def __exit__(self, typ, value, traceback):
        global execute_sync
        execute_sync = False
        if typ is not None:
            raise


class Journal(object):
    """
    Interface for accessing the journal for the queries that couldn't run in
    the remote side, either for it being offline or failed to execute.

    This should be used in a context and provides file locking by itself.
    """

    JOURNAL_FILE = '/data/ha-journal'

    @classmethod
    def is_empty(cls):
        if not os.path.exists(cls.JOURNAL_FILE):
            return True
        try:
            return os.stat(cls.JOURNAL_FILE).st_size == 0
        except OSError:
            return True

    def _get_queries(self):
        try:
            with open(self.JOURNAL_FILE, 'rb') as f:
                self.queries = pickle.loads(f.read())
        except (pickle.PickleError, EOFError):
            self.queries = []

    def __enter__(self):
        self._lock = LockFile(self.JOURNAL_FILE)
        while not self._lock.i_am_locking():
            try:
                self._lock.acquire(timeout=5)
            except LockTimeout:
                self._lock.break_lock()

        if not os.path.exists(self.JOURNAL_FILE):
            open(self.JOURNAL_FILE, 'a').close()

        self._get_queries()
        return self

    def __exit__(self, typ, value, traceback):

        with open(self.JOURNAL_FILE, 'wb+') as f:
            if self.queries:
                f.write(pickle.dumps(self.queries))

        self._lock.release()
        if typ is not None:
            raise


class RunSQLRemote(threading.Thread):
    """
    This is a thread responsible for running the queries on the remote side.

    The query will be appended to the Journal in case the Journal is not empty
    or if it fails (e.g. remote side offline)
    """

    def __init__(self, *args, **kwargs):
        self._sql = kwargs.pop('sql')
        self._params = kwargs.pop('params')
        super(RunSQLRemote, self).__init__(*args, **kwargs)

    def run(self):
        from freenasUI.middleware.notifier import notifier
        from freenasUI.common.log import log_traceback
        # FIXME: cache IP value
        s = notifier().failover_rpc()
        try:
            with Journal() as f:
                if f.queries:
                    f.queries.append((self._sql, self._params))
                else:
                    s.run_sql(self._sql, self._params)
        except socket.error as err:
            with Journal() as f:
                f.queries.append((self._sql, self._params))
            return False
        except Exception as err:
            log_traceback(log=log)
            log.error('Failed to run SQL remotely %s: %s', self._sql, err)
            return False
        return True


class DatabaseFeatures(sqlite3base.DatabaseFeatures):
    pass


class DatabaseOperations(sqlite3base.DatabaseOperations):
    pass


class DatabaseWrapper(sqlite3base.DatabaseWrapper):

    def create_cursor(self):
        return self.connection.cursor(factory=HASQLiteCursorWrapper)

    def dump_send(self):
        """
        Method responsible for dumping the database into SQL,
        excluding the tables that should not be synced between nodes.
        """
        from freenasUI.middleware.notifier import notifier
        cur = self.cursor()
        cur.executelocal("select name from sqlite_master where type = 'table'")

        script = []
        for row in cur.fetchall():
            table = row[0]
            if table in NO_SYNC_MAP:
                tbloptions = NO_SYNC_MAP.get(table)
                if not tbloptions:
                    continue
            cur.executelocal("PRAGMA table_info('%s');" % table)
            fieldnames = [i[1] for i in cur.fetchall()]
            script.append('DELETE FROM %s' % table)
            cur.executelocal('SELECT %s FROM %s' % (
                "'INSERT INTO %s (%s) VALUES (' || %s ||')'" % (
                    table,
                    ', '.join(['`%s`' % f for f in fieldnames]),
                    " || ',' || ".join(
                        ['quote(`%s`)' % field for field in fieldnames]
                    ),
                ),
                table,
            ))
            for row in cur.fetchall():
                script.append(row[0])

        s = notifier().failover_rpc()
        # If we are syncing then we need to clear the Journal in case
        # everything goes as planned.
        with Journal() as j:
            try:
                sync = s.sync_to(script)
                if sync:
                    j.queries = []
                return sync
            except (xmlrpc.client.Fault, socket.error) as e:
                log.error('Failed sync_to: %s', e)
                return False

    def dump_recv(self, script):
        """
        Receives the dump from the other side, executing via script within
        a transaction.
        """

        cur = self.cursor()
        cur.executelocal("select name from sqlite_master where type = 'table'")

        for row in cur.fetchall():
            table = row[0]
            # Skip in case table is supposed to sync
            if table not in NO_SYNC_MAP:
                continue

            # If the table has no restrictions, simply preseve the values
            # for completeness.
            # This chunck of code may not be really necessary for now.
            tbloptions = NO_SYNC_MAP.get(table)
            if not tbloptions:
                cur.executelocal("PRAGMA table_info('%s');" % table)
                fieldnames = [i[1] for i in cur.fetchall()]
                script.append('DELETE FROM %s' % table)
                cur.executelocal('SELECT %s FROM %s' % (
                    "'INSERT INTO %s (%s) VALUES (' || %s ||')'" % (
                        table,
                        ', '.join(['`%s`' % f for f in fieldnames]),
                        " || ',' || ".join(
                            ['quote(`%s`)' % field for field in fieldnames]
                        ),
                    ),
                    table,
                ))
                for row in cur.fetchall():
                    script.append(row[0])

            # If the table has fields restrictions, update these fields
            # exclusively.
            else:
                fieldnames = tbloptions['fields']
                cur.executelocal('SELECT %s FROM %s' % (
                    "'UPDATE %s SET ' || %s || ' WHERE id = ' || id" % (
                        table,
                        " || ', ' || ".join([
                            "'`%s` = ' || quote(`%s`)" % (f, f)
                            for f in fieldnames
                        ]),
                    ),
                    table,
                ))
                for row in cur.fetchall():
                    script.append(row[0])

        # Execute the script within a transaction
        cur.executescript(';'.join(
            ['PRAGMA foreign_keys=OFF', 'BEGIN TRANSACTION'] + script + [
                'COMMIT;'
            ]
        ))

        with Journal() as j:
            j.queries = []

        return True


class HASQLiteCursorWrapper(Database.Cursor):

    def execute_passive(self, query, params=None):
        """
        Process the query, modify it if necessary based on NO_SYNC_MAP rules
        and execute it on the remote side.
        """
        global execute_sync

        # Skip SELECT queries
        if query.lower().startswith('select'):
            return

        try:
            # FIXME: This is extremely time-consuming
            from freenasUI.middleware.notifier import notifier
            if not (
                hasattr(notifier, 'failover_status') and
                notifier().failover_status() == 'MASTER'
            ):
                return
        except:
            return

        parse = sqlparse.parse(query)
        for p in parse:

            # Only care for DELETE, INSERT and UPDATE queries
            if p.tokens[0].normalized not in ('DELETE', 'INSERT', 'UPDATE'):
                continue

            cparams = list(params)
            if p.tokens[0].normalized == 'INSERT':

                into = p.token_next_match(0, sqlparse.tokens.Keyword, 'INTO')
                if not into:
                    continue

                next_ = p.token_next(into)

                if next_.get_name() in NO_SYNC_MAP:
                    continue

            elif p.tokens[0].normalized == 'DELETE':

                from_ = p.token_next_match(0, sqlparse.tokens.Keyword, 'FROM')
                if not from_:
                    continue

                next_ = p.token_next(from_)

                if next_.get_name() in NO_SYNC_MAP:
                    continue

            elif p.tokens[0].normalized == 'UPDATE':

                name = p.token_next(p.tokens[0]).get_name()
                no_sync = NO_SYNC_MAP.get(name)
                # Skip if table is in set to not to sync and has no attrs
                if no_sync is None and name in NO_SYNC_MAP:
                    continue

                set_ = p.token_next_match(0, sqlparse.tokens.Keyword, 'SET')
                if not set_:
                    continue

                next_ = p.token_next(set_)
                if not next_:
                    continue

                if no_sync is None:
                    lookup = []
                else:

                    if 'fields' not in no_sync:
                        continue

                    if issubclass(
                        next_.__class__, sqlparse.sql.IdentifierList
                    ):
                        lookup = list(next_.get_sublists())
                    elif issubclass(next_.__class__, sqlparse.sql.Comparison):
                        lookup = [next_]

                    # Get all placeholders from the query (%s or ?)
                    placeholders = [a for a in p.flatten() if a.value in ('%s', '?')]

                # Remember correspondent cparams to delete
                delete_idx = []

                for l in lookup:

                    if l.get_name() not in no_sync['fields']:
                        continue

                    # Remove placeholder from the params
                    try:
                        idx = placeholders.index(l.tokens[-1])
                        if cparams:
                            delete_idx.append(idx)
                    except ValueError:
                        pass

                    # If it is a list we must also remove the comma around it
                    prev_ = l.parent.token_prev(l)
                    next_ = l.parent.token_next(l)
                    if next_ and issubclass(
                        next_.__class__, sqlparse.sql.Token
                    ) and next_.value == ',':
                        del l.parent.tokens[l.parent.token_index(next_)]
                    elif prev_ and issubclass(
                        prev_.__class__, sqlparse.sql.Token
                    ) and prev_.value == ',':
                        del l.parent.tokens[l.parent.token_index(prev_)]
                    del l.parent.tokens[l.parent.token_index(l)]

                delete_idx.sort(reverse=True)
                for i in delete_idx:
                    del cparams[i]

            if params is not None:
                sql = self.convert_query(str(p))
            else:
                sql = str(p)
            # Actually try to run the query on the remote side within a thread
            rsr = RunSQLRemote(sql=sql, params=cparams)
            rsr.start()
            if execute_sync:
                rsr.join()

    def locked_retry(self, method, *args, **kwargs):
        """
        There are multiple processes accessing the sqlite3 database
        which in turn denies concurrent accesses.
        To try to mitigate the issue we retry the query a few times
        before bailing out.
        See #19733
        """
        retries = 0
        while True:
            try:
                rv = method(self, *args, **kwargs)
            except OperationalError as e:
                if 'locked' not in str(e):
                    raise
                if retries < 5:
                    time.sleep(0.3)
                    retries += 1
                    continue
                else:
                    try:
                        from freenasUI.freeadmin.utils import log_db_locked
                        log_db_locked()
                    except Exception:
                        pass
                    raise e
            break
        return rv

    def execute(self, query, params=None):

        if params is None:
            return self.locked_retry(Database.Cursor.execute, query)
        query = self.convert_query(query)
        execute = self.locked_retry(Database.Cursor.execute, query, params)

        # Allow sync to be bypassed just to be extra safe on things like
        # database migration.
        # Alternatively a south driver could be written bu the effort would be
        # quite significant.
        skip_passive_sentinel = '/tmp/.sqlite3_ha_skip'
        skip = False
        if os.path.exists(skip_passive_sentinel):
            try:
                skip = os.stat(skip_passive_sentinel).st_uid == 0
            except OSError:
                pass
        if not skip:
            self.execute_passive(query, params=params)

        return execute

    def executelocal(self, query, params=None):
        if params is None:
            return self.locked_retry(Database.Cursor.execute, query)
        query = self.convert_query(query)
        return self.locked_retry(Database.Cursor.execute, query, params)

    def executemany(self, query, param_list):
        query = self.convert_query(query)
        return self.locked_retry(Database.Cursor.executemany, query, param_list)

    def convert_query(self, query):
        return sqlite3base.FORMAT_QMARK_REGEX.sub('?', query).replace(
            '%%', '%'
        )
