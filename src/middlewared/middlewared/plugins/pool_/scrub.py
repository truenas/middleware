import asyncio
import errno
import time

from middlewared.api import api_method, Event
from middlewared.plugins.zfs_.zfs_events import ScrubNotStartedAlert, ScrubStartedAlert
from middlewared.api.current import (
    PoolScrubEntry, PoolScrubCreateArgs, PoolScrubCreateResult, PoolScrubUpdateArgs, PoolScrubUpdateResult,
    PoolScrubDeleteArgs, PoolScrubDeleteResult, PoolScrubScrubArgs, PoolScrubScrubResult, PoolScrubRunArgs,
    PoolScrubRunResult, PoolScanChangedEvent,
)
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
from middlewared.service_exception import ValidationError
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.plugins.zpool.query_impl import query_impl


HISTORY_CREATE_IMPORT_CMDS = ('zpool create', 'zpool import')


class ScrubError(CallError):
    pass


class PoolScrubModel(sa.Model):
    __tablename__ = 'storage_scrub'

    id = sa.Column(sa.Integer(), primary_key=True)
    scrub_volume_id = sa.Column(sa.Integer(), sa.ForeignKey('storage_volume.id', ondelete='CASCADE'))
    scrub_threshold = sa.Column(sa.Integer(), default=35)
    scrub_description = sa.Column(sa.String(200))
    scrub_minute = sa.Column(sa.String(100), default='00')
    scrub_hour = sa.Column(sa.String(100), default='00')
    scrub_daymonth = sa.Column(sa.String(100), default='*')
    scrub_month = sa.Column(sa.String(100), default='*')
    scrub_dayweek = sa.Column(sa.String(100), default='7')
    scrub_enabled = sa.Column(sa.Boolean(), default=True)


class PoolScrubService(CRUDService):

    class Config:
        datastore = 'storage.scrub'
        datastore_extend = 'pool.scrub.pool_scrub_extend'
        datastore_prefix = 'scrub_'
        namespace = 'pool.scrub'
        cli_namespace = 'storage.scrub'
        role_prefix = 'POOL_SCRUB'
        entry = PoolScrubEntry
        events = [
            Event(
                name='pool.scan',
                description='Progress of pool resilver/scrub.',
                roles=['POOL_SCRUB_READ'],
                models={
                    'CHANGED': PoolScanChangedEvent,
                },
            ),
        ]

    @private
    async def pool_scrub_extend(self, data):
        pool = data.pop('volume')
        data['pool'] = pool['id']
        data['pool_name'] = pool['vol_name']
        convert_db_format_to_schedule(data)
        return data

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        pool_pk = data.get('pool')
        if pool_pk:
            pool_obj = await self.middleware.call(
                'datastore.query',
                'storage.volume',
                [('id', '=', pool_pk)]
            )

            if len(pool_obj) == 0:
                verrors.add(
                    f'{schema}.pool',
                    'The specified volume does not exist'
                )
            elif (
                'id' not in data.keys() or
                (
                    'id' in data.keys() and
                    'original_pool_id' in data.keys() and
                    pool_pk != data['original_pool_id']
                )
            ):
                scrub_obj = await self.query([('pool', '=', pool_pk)])
                if len(scrub_obj) != 0:
                    verrors.add(
                        f'{schema}.pool',
                        'A scrub with this pool already exists'
                    )

        return verrors, data

    @api_method(PoolScrubCreateArgs, PoolScrubCreateResult)
    async def do_create(self, data):
        """
        Create a scrub task for a pool.

        `threshold` refers to the minimum amount of time in days has to be passed before
        a scrub can run again.

        .. examples(websocket)::

          Create a scrub task for pool of id 1, to run every sunday but with a threshold of
          35 days.
          The check will run at 3AM every sunday.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.scrub.create"
                "params": [{
                    "pool": 1,
                    "threshold": 35,
                    "description": "Monthly scrub for tank",
                    "schedule": "0 3 * * 7",
                    "enabled": true
                }]
            }
        """
        verrors, data = await self.validate_data(data, 'pool_scrub_create')
        verrors.check()

        data['volume'] = data.pop('pool')
        convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return await self.get_instance(data['id'])

    @api_method(PoolScrubUpdateArgs, PoolScrubUpdateResult)
    async def do_update(self, id_, data):
        """
        Update scrub task of `id`.
        """
        task_data = await self.get_instance(id_)
        original_data = task_data.copy()
        task_data['original_pool_id'] = original_data['pool']
        task_data.update(data)
        verrors, task_data = await self.validate_data(task_data, 'pool_scrub_update')
        verrors.check()

        task_data.pop('original_pool_id')
        convert_schedule_to_db_format(task_data)
        convert_schedule_to_db_format(original_data)

        if len(set(task_data.items()) ^ set(original_data.items())) > 0:

            task_data['volume'] = task_data.pop('pool')
            task_data.pop('pool_name', None)

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id_,
                task_data,
                {'prefix': self._config.datastore_prefix}
            )

            await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(PoolScrubDeleteArgs, PoolScrubDeleteResult)
    async def do_delete(self, id_):
        """
        Delete scrub task of `id`.
        """
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id_
        )

        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)
        return response

    @api_method(PoolScrubScrubArgs, PoolScrubScrubResult, roles=['POOL_WRITE'])
    @job(
        description=lambda name, action="START": (
            f"Scrub of pool {name!r}" if action == "START"
            else f"{action.title()} scrubbing pool {name!r}"
        ),
        lock=lambda i: f'{i[0]}-{i[1] if len(i) >= 2 else "START"}' if i else '',
    )
    async def scrub(self, job, name, action):
        """
        Start/Stop/Pause a scrub on pool `name`.
        """
        await self.middleware.call('zfs.pool.scrub_action', name, action)

        if action == 'START':
            while True:
                scrub = await self.middleware.call('zfs.pool.scrub_state', name)

                if scrub['pause']:
                    job.set_progress(100, 'Scrub paused')
                    break

                if scrub['function'] != 'SCRUB':
                    break

                if scrub['state'] == 'FINISHED':
                    job.set_progress(100, 'Scrub finished')
                    break

                if scrub['state'] == 'CANCELED':
                    break

                if scrub['state'] == 'SCANNING':
                    job.set_progress(scrub['percentage'], 'Scrubbing')

                await asyncio.sleep(1)

    @api_method(
        PoolScrubRunArgs,
        PoolScrubRunResult,
        pass_thread_local_storage=True,
        roles=['POOL_WRITE']
    )
    def run(self, tls, name: str, threshold: int) -> None:
        """
        Initiate a scrub of pool `name` if last scrub was performed more than
        `threshold` days before.
        """
        for alert in ('ScrubNotStarted', 'ScrubStarted'):
            self.call_sync2(self.s.alert.oneshot_delete, alert, name)

        try:
            started = self._run_impl(tls, name, threshold)
        except ScrubError as e:
            self.call_sync2(
                self.s.alert.oneshot_create,
                ScrubNotStartedAlert(pool=name, text=e.errmsg),
            )
        else:
            if started:
                self.call_sync2(
                    self.s.alert.oneshot_create,
                    ScrubStartedAlert(name),
                )

    def _run_impl(self, tls, name: str, threshold: int) -> bool:
        """Return True if scrub was started, False if not needed.

        Raises ScrubError for expected pool problems (-> ScrubNotStartedAlert).
        """
        if name != self.middleware.call_sync('boot.pool_name'):
            if self.middleware.call_sync('failover.licensed'):
                if self.middleware.call_sync('failover.status') == 'BACKUP':
                    return False

            if not self.middleware.call_sync('datastore.query', 'storage.volume', [['vol_name', '=', name]]):
                raise ValidationError(
                    'pool.scrub.run',
                    f'{name!r} zpool not found in database',
                    errno.ENOENT,
                )

        info = query_impl(
            tls.lzh,
            {'pool_names': [name], 'scan': True},
            return_pool_obj=True,
        )
        if not info:
            raise ScrubError(f'Pool {name} is not imported, not running scrub')

        status, zpool_obj = info[0]

        if not status['healthy']:
            raise ScrubError(
                f'Pool {name} is not healthy ({status["status"]}), not running scrub'
            )

        scan = status['scan']
        if scan and scan['state'] == 'SCANNING':
            # Already scanning — nothing to do
            return False

        # Threshold check via scan end_time
        start_scrub = False
        cutoff = int(time.time()) - (threshold - 1) * 86400

        if (
            scan
            and scan['function'] == 'SCRUB'
            and scan['state'] == 'FINISHED'
        ):
            if scan['end_time'] >= cutoff:
                return False  # recent enough — skip
            start_scrub = True

        # Slow path: check pool history for recent create/import
        if not start_scrub:
            for entry in zpool_obj.iter_history(since=cutoff):
                cmd = entry.get('history command', '')
                if any(s in cmd for s in HISTORY_CREATE_IMPORT_CMDS):
                    self.logger.trace(
                        'Pool %r recent create/import within threshold window',
                        name,
                    )
                    break
            else:
                start_scrub = True

        if not start_scrub:
            return False

        self.middleware.call_sync('zpool.scrub.run_impl', name, 'SCRUB', 'START')
        return True
