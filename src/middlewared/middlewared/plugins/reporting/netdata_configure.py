import os
import subprocess

from middlewared.service import private, Service

from .utils import get_netdata_state_path


class ReportingService(Service):

    @private
    def netdata_storage_location(self):
        systemdataset_config = self.middleware.call_sync('systemdataset.config')
        if not systemdataset_config['path']:
            return None

        return f'{systemdataset_config["path"]}/netdata'

    @private
    def netdata_state_location(self):
        # We don't check if system dataset is properly configured here because netdata conf won't be generated
        # if storage location is not properly configured which we check in the netdata etc file.
        return get_netdata_state_path()

    @private
    def post_dataset_mount_action(self):
        if os.path.exists(get_netdata_state_path()):
            return

        cp = subprocess.run(
            ['cp', '-a', '/var/lib/netdata', get_netdata_state_path()], check=False, capture_output=True,
        )
        if cp.returncode != 0:
            self.logger.error('Failed to copy netdata state over from /var/lib/netdata: %r', cp.stderr.decode())
            # We want to make sure this path exists always regardless of an error so that
            # at least netdata can start itself gracefully
            os.makedirs(get_netdata_state_path(), exist_ok=True)

    @private
    async def start_service(self):
        if await self.middleware.call('failover.licensed'):
            return

        await self.middleware.call('service.start', 'netdata')
