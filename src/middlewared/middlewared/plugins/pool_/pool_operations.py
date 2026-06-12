import datetime
import errno
from dataclasses import dataclass

from truenas_pylibzfs import ZFSError, ZFSException

from middlewared.api import api_method
from middlewared.api.current import PoolScrubArgs, PoolScrubResult, PoolUpgradeArgs, PoolUpgradeResult
from middlewared.plugins.zpool import upgrade_zpool_impl
from middlewared.service import Service, job, private
from middlewared.service_exception import ValidationError


@dataclass(frozen=True)
class ResilverPriority:
    """ZFS tunables written to sysfs to control resilver/scrub aggressiveness."""
    resilver_min_time_ms: int
    nia_credit: int
    nia_delay: int
    scrub_max_active: int


# Applied while inside the user-configured off-peak window (resilver favored).
HIGH_PRIORITY = ResilverPriority(resilver_min_time_ms=3000, nia_credit=10, nia_delay=2, scrub_max_active=8)
# Applied outside the off-peak window (production I/O favored).
LOW_PRIORITY = ResilverPriority(resilver_min_time_ms=1500, nia_credit=5, nia_delay=5, scrub_max_active=3)


def calculate_resilver_priority(
    resilver: dict, now: datetime.datetime | None = None
) -> ResilverPriority:
    """
    Determine the ZFS resilver tunables for a resilver configuration.

    Returns ``HIGH_PRIORITY`` when ``now`` falls inside the configured off-peak
    window (`begin`/`end`/`weekday`), otherwise ``LOW_PRIORITY``. ``now`` defaults
    to the current local time and exists primarily so the decision is testable.

    `weekday` is a comma separated string of isoweekday values (1=Mon .. 7=Sun).
    If `begin` > `end` the window rolls over midnight into the following morning.
    """
    if now is None:
        now = datetime.datetime.now()

    higher_prio = False
    weekdays = [int(x) for x in resilver['weekday'].split(',')]
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

    return HIGH_PRIORITY if higher_prio else LOW_PRIORITY


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

        priority = calculate_resilver_priority(resilver)

        with open('/sys/module/zfs/parameters/zfs_resilver_min_time_ms', 'w') as f:
            f.write(str(priority.resilver_min_time_ms))
        with open('/sys/module/zfs/parameters/zfs_vdev_nia_credit', 'w') as f:
            f.write(str(priority.nia_credit))
        with open('/sys/module/zfs/parameters/zfs_vdev_nia_delay', 'w') as f:
            f.write(str(priority.nia_delay))
        with open('/sys/module/zfs/parameters/zfs_vdev_scrub_max_active', 'w') as f:
            f.write(str(priority.scrub_max_active))

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
            self.call_sync2(self.s.alert.oneshot_delete, 'PoolUpgraded', pname)
            self.middleware.call_sync('zpool.send_change_event', pname, 'CHANGED')
            return True
