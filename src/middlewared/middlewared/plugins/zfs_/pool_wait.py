import libzfs

from middlewared.schema import accepts, Dict, Str
from middlewared.service import CallError, Service


POOL_ACTIVITY_TYPES = [a.name for a in libzfs.ZpoolWaitActivity]


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    @accepts(
        Str('pool_name'),
        Dict(
            'options',
            Str('activity_type', enum=POOL_ACTIVITY_TYPES, required=True),
        )
    )
    def wait(self, pool_name, options):
        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(pool_name)
                pool.wait(options['activity_type'])
        except libzfs.ZFSException as e:
            raise CallError(str(e))
