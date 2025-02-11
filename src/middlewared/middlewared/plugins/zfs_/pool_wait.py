import libzfs

from middlewared.service import CallError, Service
from middlewared.service_exception import ValidationError


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def wait(self, pool_name: str, options: dict):
        """Wait on zpool operations to complete.

        Args:
            pool_name: (required) str the name of the zpool
            options: (required) dictionary with a top-level key of
                "activity_type" whose value may be one of
                the values in `libzfs.ZpoolWaitActivity`
        """
        avail = tuple([a.name for a in libzfs.ZpoolWaitActivity])
        if options['activity_type'] not in avail:
            raise ValidationError(
                'activity_type',
                f'{options["activity_type"]!r} not a valid type. Must be one of {", ".join(avail)}'
            )

        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(pool_name)
                pool.wait(options['activity_type'])
        except libzfs.ZFSException as e:
            raise CallError(str(e))
