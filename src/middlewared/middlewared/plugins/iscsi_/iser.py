import subprocess

from middlewared.service import Service

KERNEL_MODULE = 'isert_scst'


class iSCSITargetISERService(Service):
    """
    Support iSER configuration.
    """
    class Config:
        private = True
        namespace = 'iscsi.iser'

    async def before_start(self):
        if await self.middleware.call('iscsi.global.iser_enabled'):
            await self.middleware.run_in_thread(self._load_kernel_module)

    def _load_kernel_module(self):
        subprocess.run(['modprobe', KERNEL_MODULE])
