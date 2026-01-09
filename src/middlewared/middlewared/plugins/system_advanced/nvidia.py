import os
import subprocess

from middlewared.service import private, Service
from middlewared.utils.gpu import set_nvidia_persistence_mode


class SystemAdvancedService(Service):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'

    @private
    async def handle_nvidia_toggle(self):
        # this only gets called if nvidia setting was toggled
        # which means we need to restart apps once we have run our configuration logic
        await self.middleware.call('system.advanced.configure_nvidia')
        if (await self.middleware.call('docker.config'))['pool']:
            # We explicitly have it non-blocking here as docker restart on HDD based systems can take
            # decent amount of time
            self.middleware.create_task(self.middleware.call('docker.restart_svc'))

    @private
    def configure_nvidia(self):
        config = self.middleware.call_sync('system.advanced.config')
        nvidia_sysext_path = '/run/extensions/nvidia.raw'
        if config['nvidia'] and not os.path.exists(nvidia_sysext_path):
            os.makedirs('/run/extensions', exist_ok=True)
            os.symlink('/usr/share/truenas/sysext-extensions/nvidia.raw', nvidia_sysext_path)
            refresh = True
        elif not config['nvidia'] and os.path.exists(nvidia_sysext_path):
            os.unlink(nvidia_sysext_path)
            refresh = True
        else:
            refresh = False

        if refresh:
            subprocess.run(['systemd-sysext', 'refresh'], capture_output=True, check=True, text=True)
            subprocess.run(['ldconfig'], capture_output=True, check=True, text=True)

        if config['nvidia']:
            cp = subprocess.run(
                ['modprobe', '-a', 'nvidia', 'nvidia_drm', 'nvidia_modeset'],
                capture_output=True,
                text=True
            )
            if cp.returncode != 0:
                self.logger.error('Error loading nvidia driver: %s', cp.stderr)
            else:
                set_nvidia_persistence_mode(config['nvidia_persistence_mode'])


async def setup(middleware):
    try:
        await middleware.call('system.advanced.configure_nvidia')
    except Exception:
        middleware.logger.error('Unhandled exception configuring nvidia', exc_info=True)
