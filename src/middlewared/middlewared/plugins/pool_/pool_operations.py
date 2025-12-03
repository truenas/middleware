from datetime import datetime

from middlewared.api import api_method
from middlewared.api.current import PoolScrubArgs, PoolScrubResult, PoolUpgradeArgs, PoolUpgradeResult
from middlewared.service import job, private, Service


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
        now = datetime.now()
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
            resilver_min_time_ms = 9000
            nia_credit = 10
            nia_delay = 2
            scrub_max_active = 8
        else:
            resilver_min_time_ms = 3000
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

    @api_method(PoolUpgradeArgs, PoolUpgradeResult, roles=['POOL_WRITE'])
    async def upgrade(self, oid):
        """
        Upgrade pool of `id` to latest version with all feature flags.

        .. examples(websocket)::

          Upgrade pool of id 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.upgrade",
                "params": [1]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        # Should we check first if upgrade is required ?
        await self.middleware.call('zfs.pool.upgrade', pool['name'])
        await self.middleware.call('alert.oneshot_delete', 'PoolUpgraded', pool['name'])
        return True
