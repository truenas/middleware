import os
import subprocess
import uuid

from middlewared.utils import BOOTREADY

from .utils import FIRST_INSTALL_SENTINEL, FIRST_INSTALL_BE, lifecycle_conf


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

        root_ds = middleware.call_sync('filesystem.mount_info', [['mountpoint', '=', '/']], {'get': True})
        # Creating pristine boot environment from the "default"
        middleware.logger.info('Creating %r boot environment...', FIRST_INSTALL_BE)
        try:
            middleware.call_sync('bootenv.create', {'name': FIRST_INSTALL_BE, 'source': root_ds['mount_source']})
        except Exception:
            middleware.logger.error('Failed to create initial boot environment', exc_info=True)
        else:
            boot_pool = middleware.call_sync('boot.pool_name')
            cp = subprocess.run(
                ['zfs', 'set', 'zectl:keep=True', os.path.join(boot_pool, 'ROOT/Initial-Install')], capture_output=True
            )
            if cp.returncode != 0:
                middleware.logger.error(
                    'Failed to set keep attribute for Initial-Install boot environment: %s', cp.stderr.decode()
                )


async def setup(middleware):
    lifecycle_conf.SYSTEM_BOOT_ID = str(uuid.uuid4())
    middleware.event_register('system.ready', 'Finished boot process')
    middleware.event_register('system.reboot', 'Started reboot process')
    middleware.event_register('system.shutdown', 'Started shutdown process')

    await middleware.run_in_thread(firstboot, middleware)

    settings = await middleware.call('system.general.config')
    middleware.logger.debug('Setting timezone to %r', settings['timezone'])
    await middleware.call('core.environ_update', {'TZ': settings['timezone']})
    await middleware.call('system.general.set_language')
    await middleware.call('sysctl.set_zvol_volmode', 2)
