import pyudev
import subprocess
import time

from middlewared.service import private, Service
from middlewared.utils import run, start_daemon_thread


class DeviceService(Service):

    @private
    async def settle_udev_events(self):
        cp = await run(['udevadm', 'settle'], stdout=subprocess.DEVNULL, check=False)
        if cp.returncode != 0:
            self.middleware.logger.error('Failed to settle udev events: %s', cp.stderr.decode())


def udev_events(middleware):
    while True:
        # We always want to keep polling udev, let's log what error we are
        # seeing and fix them accordingly as we see them
        try:
            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem='block')
            monitor.filter_by(subsystem='net')
            for device in iter(monitor.poll, None):
                middleware.call_hook_sync(
                    f'udev.{device.subsystem}', data={**dict(device), 'SYS_NAME': device.sys_name}
                )
        except Exception:
            middleware.logger.error('Polling udev failed', exc_info=True)
            time.sleep(10)


def setup(middleware):
    start_daemon_thread(target=udev_events, args=(middleware,))
