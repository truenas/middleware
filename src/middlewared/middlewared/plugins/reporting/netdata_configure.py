import json
import os
import subprocess

from middlewared.service import private, Service

from .utils import get_netdata_state_path, NETDATA_UPS_INFO_FILE, NETDATA_GID, NETDATA_UID


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
    def generate_netdata_ups_info_file(self):
        netdata_storage_location = self.netdata_storage_location()
        if not netdata_storage_location:
            return

        ups_config = self.middleware.call_sync('ups.config')
        file_path = os.path.join(netdata_storage_location, NETDATA_UPS_INFO_FILE)

        remote_addr = ''
        if ups_config['remotehost'] and ups_config['remoteport']:
            remote_addr = f'{ups_config["remotehost"]}:{ups_config["remoteport"]}'

        with open(file_path, 'w') as w:
            w.write(json.dumps({
                'remote_addr': remote_addr,
            }))

        os.chown(file_path, NETDATA_UID, NETDATA_GID)
        os.chmod(file_path, 0o770)

    @private
    async def start_service(self):
        if await self.middleware.call('failover.licensed'):
            return

        await self.middleware.call('service.start', 'netdata')
