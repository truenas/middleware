import os
import shutil


def localtime_configuration(middleware):
    system_config = middleware.call_sync('system.general.config')
    if not system_config['timezone']:
        system_config['timezone'] = 'America/Los_Angeles'

    shutil.copy(
        os.path.join('/usr/share/zoneinfo/', system_config['timezone']),
        '/etc/localtime'
    )

    with open('/var/db/zoneinfo', 'w') as f:
        f.write(f'{system_config["timezone"]}\n')


async def render(service, middleware):
    await middleware.run_in_thread(localtime_configuration, middleware)
