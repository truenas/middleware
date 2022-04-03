# -*- coding=utf-8 -*-
import os
import textwrap
import uuid

from middlewared.utils import run

from .utils import FIRST_INSTALL_SENTINEL, lifecycle_conf


async def firstboot(middleware):
    if os.path.exists(FIRST_INSTALL_SENTINEL):
        lifecycle_conf.SYSTEM_FIRST_BOOT = True
        # Delete sentinel file before making clone as we
        # we do not want the clone to have the file in it.
        os.unlink(FIRST_INSTALL_SENTINEL)

        if await middleware.call('system.is_enterprise'):
            config = await middleware.call('datastore.config', 'system.advanced')
            await middleware.call('datastore.update', 'system.advanced', config['id'], {'adv_autotune': True})

        # Creating pristine boot environment from the "default"
        initial_install_be = 'Initial-Install'
        middleware.logger.info('Creating %r boot environment...', initial_install_be)
        activated_be = await middleware.call('bootenv.query', [['activated', '=', True]], {'get': True})
        try:
            await middleware.call('bootenv.create', {'name': initial_install_be, 'source': activated_be['realname']})
        except Exception:
            middleware.logger.error('Failed to create initial boot environment', exc_info=True)
        else:
            boot_pool = await middleware.call('boot.pool_name')
            cp = await run('zfs', 'set', 'zectl:keep=True', os.path.join(boot_pool, 'ROOT/Initial-Install'))
            if cp.returncode != 0:
                middleware.logger.error(
                    'Failed to set keep attribute for Initial-Install boot environment: %s', cp.stderr.decode()
                )


async def setup(middleware):
    lifecycle_conf.SYSTEM_BOOT_ID = str(uuid.uuid4())

    middleware.event_register('system', textwrap.dedent('''\
        Sent on system state changes.

        id=ready -- Finished boot process\n
        id=reboot -- Started reboot process\n
        id=shutdown -- Started shutdown process'''))

    if os.path.exists('/tmp/.bootready'):
        lifecycle_conf.SYSTEM_READY = True
    else:
        await firstboot(middleware)

    settings = await middleware.call('system.general.config')
    await middleware.call('core.environ_update', {'TZ': settings['timezone']})

    middleware.logger.debug(f'Timezone set to {settings["timezone"]}')

    await middleware.call('system.general.set_language')
    await middleware.call('system.general.set_crash_reporting')

    CRASH_DIR = '/data/crash'
    os.makedirs(CRASH_DIR, exist_ok=True)
    os.chmod(CRASH_DIR, 0o775)

    await middleware.call('sysctl.set_zvol_volmode', 2)
