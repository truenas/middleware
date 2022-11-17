import shutil

from middlewared.service import Service
from .utils import GlusterConfig


class GlusterBackupService(Service):

    class Config:
        namespace = 'gluster.backup'
        private = True

    def restore(self, src):
        # NOTE: this method is called from config.upload and within
        # context of a `with tempfile` so the src is decompressed and
        # on disk to be manipulated. We don't restart the glusterd
        # service because it's expected that this method is _only_
        # called from config.upload and the calling method has logic
        # to reboot this node, which will start back the necessary
        # services at boot time

        # stop the service if it's already running
        # this isn't technically needed but better to be safe
        if self.middleware.call_sync('service.started', 'glusterd'):
            self.middleware.call_sync('service.stop', 'glusterd')

        # copy contents to destination
        shutil.copytree(src, GlusterConfig.WORKDIR.value, dirs_exist_ok=True)
