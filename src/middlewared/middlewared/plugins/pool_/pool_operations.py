import datetime
import errno

from middlewared.api import api_method
from middlewared.api.current import PoolScrubArgs, PoolScrubResult, PoolUpgradeArgs, PoolUpgradeResult
from middlewared.service import job, private, Service
from middlewared.service_exception import ValidationError
from middlewared.plugins.zpool import upgrade_zpool_impl

from truenas_pylibzfs import ZFSError, ZFSException


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @private
    def configure_resilver_priority(self):
        """
        Configure resilver priority based on user selected off-peak hours.
        """
        resilver = self.middleware.call_sync('datastore.config', 'storage.resilver')

        if not resilver['enabled'] or not resilver['weekday']:
            return

        higher_prio = False
        weekdays = map(lambda x: int(x), resilver['weekday'].split(','))
        now = datetime.datetime.now()
        now_t = now.time()
        # end overlaps the day
        if resilver['begin'] > resilver['end']:
            if now.isoweekday() in weekdays and now_t >= resilver['begin']:
                higher_prio = True
            else:
                lastweekday = now.isoweekday() - 1
                if lastweekday == 0:
                    lastweekday = 7
                if lastweekday in weekdays and now_t < resilver['end']:
                    higher_prio = True
        # end does not overlap the day
        else:
            if now.isoweekday() in weekdays and now_t >= resilver['begin'] and now_t < resilver['end']:
                higher_prio = True

        if higher_prio:
            resilver_min_time_ms = 3000
            nia_credit = 10
            nia_delay = 2
            scrub_max_active = 8
        else:
            resilver_min_time_ms = 1500
            nia_credit = 5
            nia_delay = 5
            scrub_max_active = 3

        with open('/sys/module/zfs/parameters/zfs_resilver_min_time_ms', 'w') as f:
            f.write(str(resilver_min_time_ms))
        with open('/sys/module/zfs/parameters/zfs_vdev_nia_credit', 'w') as f:
            f.write(str(nia_credit))
        with open('/sys/module/zfs/parameters/zfs_vdev_nia_delay', 'w') as f:
            f.write(str(nia_delay))
        with open('/sys/module/zfs/parameters/zfs_vdev_scrub_max_active', 'w') as f:
            f.write(str(scrub_max_active))

    @api_method(PoolScrubArgs, PoolScrubResult, roles=['POOL_WRITE'])
    @job(transient=True)
    async def scrub(self, job, oid, action):
        """
        Performs a scrub action to pool of `id`.

        `action` can be either of "START", "STOP" or "PAUSE".

        .. examples(websocket)::

          Start scrub on pool of id 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.scrub",
                "params": [1, "START"]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        return await job.wrap(await self.middleware.call('pool.scrub.scrub', pool['name'], action))

    @api_method(
        PoolUpgradeArgs,
        PoolUpgradeResult,
        pass_thread_local_storage=True,
        roles=['POOL_WRITE']
    )
    def upgrade(self, tls, oid):
        """
        Upgrade pool of `id` to latest version with all feature flags.

        Queries the database for the pool matching the given `id`, then
        enables all supported ZFS feature flags on the pool. This is a
        one-way operation and cannot be reversed. Once upgraded, the pool
        will not be importable on systems running older ZFS versions that
        do not support the newly enabled features.

        Raises a `ValidationError` if no pool matches the given `id` or
        if the pool is not currently imported.
        """
        pool = self.middleware.call_sync(
            'datastore.query', 'storage.volume', [['id', '=', oid]]
        )
        if not pool:
            raise ValidationError(
                'pool.upgrade',
                f'pool with database id {oid!r} does not exist',
                errno.ENOENT
            )

        pname = pool[0]['vol_name']
        try:
            upgrade_zpool_impl(tls.lzh, pname)
        except ZFSException as e:
            if e.code == ZFSError.EZFS_NOENT:
                raise ValidationError(
                    'pool.upgrade',
                    f'pool {pname!r} is not imported',
                    errno.ENOENT
                )
            raise
        else:
            self.middleware.call_sync('alert.oneshot_delete', 'PoolUpgraded', pname)
            return True
