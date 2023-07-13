import errno

from glustercli.cli import volume
from middlewared.service import Service, CallError, job
from middlewared.plugins.cluster_linux.utils import CTDBConfig


CRE_OR_DEL_LOCK = CTDBConfig.CRE_OR_DEL_LOCK.value
LEGACY_CTDB_VOL_NAME = CTDBConfig.LEGACY_CTDB_VOL_NAME.value


class CtdbSharedVolumeService(Service):

    class Config:
        namespace = 'ctdb.shared.volume'
        private = True

    async def config(self):
        return await self.middleware.call('ctdb.root_dir.config')

    @job()
    async def create(self, job, data):
        """
        This stub of a method exists to catch legacy versions of TrueCommand that will attempt
        to directly call ctdb.shared.volume.create prior to creation of a new gluster volume.
        """
        raise CallError(
            "This cluster-related API endpoint has been deprecated. Receiving this error message "
            "may indicate that a legacy version of TrueCommand is being used to attempt to create "
            "a SCALE cluster. If this is the case, then please update to the latest stable version "
            "of TrueCommand in order to cleanly build a new TrueNAS SCALE cluster.",
            errno.EOPNOTSUPP
        )

    @job(lock=CRE_OR_DEL_LOCK)
    async def delete(self, job):
        """
        Delete and unmount the shared volume used by ctdb daemon.
        """
        # nothing to delete if it doesn't exist
        info = await self.middleware.call('gluster.volume.exists_and_started', LEGACY_CTDB_VOL_NAME)
        if not info['exists']:
            return

        # stop the gluster volume
        if info['started']:
            options = {'args': (LEGACY_CTDB_VOL_NAME,), 'kwargs': {'force': True}}
            job.set_progress(33, f'Stopping gluster volume {LEGACY_CTDB_VOL_NAME!r}')
            await self.middleware.call('gluster.method.run', volume.stop, options)

        # finally, we delete it
        job.set_progress(66, f'Deleting gluster volume {LEGACY_CTDB_VOL_NAME!r}')
        await self.middleware.call('gluster.method.run', volume.delete, {'args': (LEGACY_CTDB_VOL_NAME,)})
        job.set_progress(100, f'Successfully deleted {LEGACY_CTDB_VOL_NAME!r}')

    @job(lock=CRE_OR_DEL_LOCK)
    async def teardown(self, job, force=False):
        """
        This is a legacy method that may be called by old versions of TrueCommand
        """
        raise CallError(
            "This cluster-related API endpoint has been deprecated. Receiving this error message "
            "may indicate that a legacy version of TrueCommand is being used to attempt to destroy "
            "a SCALE cluster. If this is the case, then please update to the latest stable version "
            "of TrueCommand in order to cleantly tear down the TrueNAS SCALE cluster.",
            errno.EOPNOTSUPP
        )
