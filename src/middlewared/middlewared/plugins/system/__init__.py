import os
import uuid

from middlewared.utils import BOOTREADY
from middlewared.utils.lifecycle import lifecycle_conf

from .utils import FIRST_INSTALL_SENTINEL


def firstboot(middleware):
    if os.path.exists(BOOTREADY):
        lifecycle_conf.SYSTEM_READY = True
    elif os.path.exists(FIRST_INSTALL_SENTINEL):
        lifecycle_conf.SYSTEM_FIRST_BOOT = True
        # Delete sentinel file before making clone as we
        # we do not want the clone to have the file in it.
        os.unlink(FIRST_INSTALL_SENTINEL)

        if middleware.call_sync('system.is_enterprise'):
            config = middleware.call_sync('datastore.config', 'system.advanced')
            middleware.call_sync('datastore.update', 'system.advanced', config['id'], {'adv_autotune': True})


def read_system_boot_id(middleware):
    try:
        with open('/proc/sys/kernel/random/boot_id', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        middleware.logger.error('Failed to read boot_id from /proc/sys/kernel/random/boot_id')
        return str(uuid.uuid4())


async def setup(middleware):
    lifecycle_conf.SYSTEM_BOOT_ID = await middleware.run_in_thread(read_system_boot_id, middleware)
    middleware.event_register('system.ready', 'Finished boot process')
    middleware.event_register('system.reboot', 'Started reboot process')
    middleware.event_register('system.shutdown', 'Started shutdown process')

    await middleware.run_in_thread(firstboot, middleware)

    settings = await middleware.call('system.general.config')
    middleware.logger.debug('Setting timezone to %r', settings['timezone'])
    await middleware.call('core.environ_update', {'TZ': settings['timezone']})
    await middleware.call('system.general.set_language')
    await middleware.call('sysctl.set_zvol_volmode', 2)
