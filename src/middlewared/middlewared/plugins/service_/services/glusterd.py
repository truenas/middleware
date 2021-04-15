import asyncio

import psutil

from .base import SimpleService
from middlewared.plugins.cluster_linux.utils import CTDBConfig

CTDB_VOL = CTDBConfig.CTDB_VOL_NAME.value


class GlusterdService(SimpleService):

    name = 'glusterd'
    systemd_unit = 'glusterd'

    restartable = True

    async def after_start(self):
        mount_job = await self.middleware.call('gluster.fuse.mount', {'all': True})
        await mount_job.wait()
        if await self.middleware.call('gluster.fuse.is_mounted', {'name': CTDB_VOL}):
            await self.middleware.call('service.start', 'ctdb')

    async def after_restart(self):
        await self.middleware.call('service.restart', 'glustereventsd')

    async def before_stop(self):
        await self.middleware.call('service.stop', 'ctdb')
        umount_job = await self.middleware.call('gluster.fuse.umount', {'all': True})
        await umount_job.wait()

    async def after_stop(self):
        await self.middleware.call('service.stop', 'glustereventsd')

        # systemd[1]: glusterd.service: Unit process 1376703 (glusterfsd) remains running after unit stopped.
        # systemd[1]: glusterd.service: Unit process 1376720 (glusterfs) remains running after unit stopped.
        # This prevents from tank/.system/ctdb_shared_vol from being unmounted
        futures = [self.middleware.call('service.terminate_process', pid)
                   for pid in await self.middleware.run_in_thread(self._glusterd_pids)]
        if futures:
            await asyncio.wait(futures)

    def _glusterd_pids(self):
        pids = []
        for process in psutil.process_iter(attrs=['cmdline']):
            if process.info['cmdline']:
                if process.info['cmdline'][0].endswith(('/glusterd', '/glusterfs', '/glusterfsd')):
                    pids.append(process.pid)
        return pids
