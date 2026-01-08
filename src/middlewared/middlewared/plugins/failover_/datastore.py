# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from datetime import datetime
import os
import time

from middlewared.service import Service
from middlewared.plugins.config import FREENAS_DATABASE
from middlewared.plugins.datastore.connection import thread_pool
from middlewared.utils.threading import start_daemon_thread, set_thread_name
from middlewared.utils import db as db_utils

FREENAS_DATABASE_REPLICATED = f'{FREENAS_DATABASE}.replicated'
RAISE_ALERT_SYNC_RETRY_TIME = 1200  # 20mins (some platforms take 15-20mins to reboot)


class FailoverDatastoreService(Service):

    class Config:
        namespace = 'failover.datastore'
        private = True
        thread_pool = thread_pool

    async def sql(self, data, sql, params):
        if await self.middleware.call('system.version') != data['version']:
            return

        if await self.middleware.call('failover.status') != 'BACKUP':
            # We can't query failover.status on `MASTER` node (please see `hook_datastore_execute_write` for
            # explanations). Non-BACKUP nodes are responsible for checking their failover status.
            return

        # TrueNAS API client JSON parser unparses all datetimes as offset-aware. We don't want to store offset-aware
        # datetimes in the database, so let's strip `tzinfo`.
        params = [p.replace(tzinfo=None) if isinstance(p, datetime) else p for p in params]

        await self.middleware.call('datastore.execute', sql, params)

    failure = False

    def is_failure(self):
        return self.failure

    def set_failure(self):
        if self.failure:
            return

        self.failure = True
        try:
            # This is executed in `hook_datastore_execute_write` so we can't query local failover status here, and we'll
            # have to rely on remote.
            if (fs := self.middleware.call_sync('failover.call_remote', 'failover.status')) == 'BACKUP':
                self.send()
            else:
                # Avoid sending database if we are not MASTER.
                self.logger.warning('Remote node failover status is %s while retrying database send', fs)
                self.failure = False
        except Exception as e:
            self.logger.warning('Error sending database to remote node on first replication failure: %r', e)

            def send_retry():
                set_thread_name('failover_datastore')

                raise_alert_time = RAISE_ALERT_SYNC_RETRY_TIME
                total_mins = raise_alert_time / 60
                sleep_time = 30
                while True:
                    raise_alert_time -= sleep_time
                    time.sleep(sleep_time)

                    if not self.failure:
                        # Someone sent the database for us
                        return

                    if (fs := self.middleware.call_sync('failover.status')) != 'MASTER':
                        self.logger.warning('Failover status is %s while retrying database send', fs)
                        self.failure = False
                        break

                    try:
                        self.middleware.call_sync('failover.datastore.send')
                    except Exception:
                        pass

                    if raise_alert_time <= 0 and self.failure:
                        self.middleware.call_sync('alert.oneshot_create', 'FailoverSyncFailed', {'mins': total_mins})
                        raise_alert_time = RAISE_ALERT_SYNC_RETRY_TIME

            start_daemon_thread(name="fo_db_retry", target=send_retry)

    def send(self):
        token = self.middleware.call_sync('failover.call_remote', 'auth.generate_token', [
            300,  # ttl
            {},  # Attributes (not required for file uploads)
            True,  # match origin
            True,  # single-use (required if STIG enabled)
        ])
        self.middleware.call_sync('failover.send_file', token, FREENAS_DATABASE, FREENAS_DATABASE_REPLICATED, {'mode': db_utils.FREENAS_DATABASE_MODE})
        self.middleware.call_sync('failover.call_remote', 'failover.datastore.receive')

        self.failure = False
        self.middleware.call_sync('alert.oneshot_delete', 'FailoverSyncFailed', None)

    def receive(self):
        # Take the following example:
        # 1. upgrade both HA controllers
        # 2. standby controller reboots (by design) into the new OS version
        # 3. active controller does NOT reboot (by design)
        # 4. for some unpredictable reason, upgrade is not "finalized"
        #   (i.e. reboot the active to failover to the newly upgraded controller, etc)
        # 5. User (or something inside middleware) makes a change to the database on the active
        #   (remember it's running the "old" version compared to the standby)
        # 6. active controller makes changes to local db or the user decides to "sync to peer"
        # 7. active controller replicates the entire database to the standby
        # 8. because the standby is running a newer version, then the schema migrations that could
        #   have occurred on the standby are now lost because the database was replaced _entirely_
        #   with a copy from the active controller (running an old version)
        #
        # The worst part about this scenario is that the standby controller will continue to run
        # without issue until:
        # 1. a change is made on the standby that tries to reference the new schema
        # 2. OR the standby controller reboots (or middlewared service restarts)
        #
        # If either of these occur, middlewared service will fail to start and crash early in startup
        # because the newer middleware will try to query the database referencing the potential changes
        # that occurred in the schema migration of the upgrade. There is no easy solution to this problem
        # once you're in this state outside of rolling back to the previous BE and performing a much more
        # disruptive upgrade. (i.e. booting the ISO and performing an upgrade that way so db replication
        # doesn't occur since middlewared service isn't running) (i.e. take the entire system down)
        #
        # To prevent this, we check to make sure the local database alembic revision matches the replicated
        # database that has been sent to us.
        loc_vers = db_utils.query_config_table('alembic_version')['version_num']
        rep_vers = db_utils.query_config_table('alembic_version', FREENAS_DATABASE_REPLICATED)['version_num']
        if loc_vers != rep_vers:
            self.logger.warning(
                'Received database alembic revision (%s) does not match local database alembic revision (%s)',
                rep_vers, loc_vers
            )
            return

        os.rename(FREENAS_DATABASE_REPLICATED, FREENAS_DATABASE)
        self.middleware.call_sync('datastore.setup')

    async def force_send(self):
        if await self.middleware.call('failover.status') == 'MASTER':
            await self.middleware.call('failover.datastore.set_failure')


def hook_datastore_execute_write(middleware, sql, params, options):
    # This code is executed in SQLite thread and blocks it (in order to avoid replication query race conditions)
    # No switching to the async context that will yield to database queries is allowed here as it will result in
    # a deadlock. That's why we can't query failover status and will always try to replicate all queries to the other
    # node. The other node will check its own failover status upon receiving them.

    if not options['ha_sync']:
        return

    if not middleware.call_sync('failover.licensed'):
        return

    if middleware.call_sync('failover.datastore.is_failure'):
        return

    try:
        middleware.call_sync(
            'failover.call_remote',
            'failover.datastore.sql',
            [
                {
                    'version': middleware.call_sync('system.version'),
                },
                sql,
                params,
            ],
            {
                'timeout': 10,
            },
        )
    except Exception as e:
        middleware.logger.warning('Error replicating SQL on the remote node: %r', e)
        middleware.call_sync('failover.datastore.set_failure')


async def setup(middleware):
    if not await middleware.call('system.is_enterprise'):
        return

    middleware.register_hook('datastore.post_execute_write', hook_datastore_execute_write, inline=True)
