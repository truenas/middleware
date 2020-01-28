import pyudev

from middlewared.utils import start_daemon_thread


def udev_events(middleware):
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='block')
    monitor.filter_by(subsystem='net')
    for device in iter(monitor.poll, None):
        middleware.call_hook_sync(f'udev.{device.subsystem}', data={**dict(device), 'SYS_NAME': device.sys_name})


def setup(middleware):
    start_daemon_thread(target=udev_events, args=(middleware,))
