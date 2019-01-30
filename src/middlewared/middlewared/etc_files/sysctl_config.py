import os
import subprocess


def set_autotune_sysctl(middleware):
    autotune_path = '/usr/local/bin/autotune'
    if os.access(autotune_path, os.X_OK):
        if middleware.call_sync('system.is_freenas'):
            ret = subprocess.run(
                [
                    autotune_path, '-o', '--kernel-reserved=1073741824',
                    '--userland-reserved=2417483648', '--conf', 'sysctl'
                ], capture_output=True
            )
        else:
            ret = subprocess.run(
                [
                    autotune_path, '-o', '--kernel-reserved=6442450944',
                    '--userland-reserved=4831838208', '--conf', 'sysctl'
                ], capture_output=True
            )

        if ret.returncode:
            middleware.logger.debug(f'Failed to set autotune sysctl values')


def sysctl_configuration(middleware):
    status = middleware.call_sync('etc.get_args')
    if not status or (status and status[0] == 'start'):
        set_autotune_sysctl(middleware)

    tuneables = middleware.call_sync('tunable.query', [['enabled', '=', True], ['type', '=', 'SYSCTL']])
    for tuneable in tuneables:
        ret = subprocess.run(
            ['sysctl', f'{tuneable["var"]}="{tuneable["value"]}"'],
            capture_output=True
        )
        if ret.returncode:
            middleware.logger.debug(f'Failed to set sysctl {tuneable["var"]} -> {tuneable["value"]}')


async def render(service, middleware):
    await middleware.run_in_thread(sysctl_configuration, middleware)
