import subprocess
from pathlib import Path

CONF_FILE = Path('/etc/sysctl.d/tunables.conf')


def setup(middleware):
    to_write = {}
    sysdefs = middleware.call_sync('tunable.get_system_defaults')
    for tun in filter(lambda x: x in sysdefs, (middleware.call_sync('tunable.query', [['type', '=', 'SYSCTL']]))):
        if tun['enabled'] and (sysdefs[tun['var']] != tun['value']):
            # tunable is enabled and the variable's value set by the end-user doesn't match what the system's
            # default value is so change it
            to_write[tun['var']] = tun['value']

    if not to_write:
        # no tunables or all disabled so make sure the config file is removed
        CONF_FILE.unlink(missing_ok=True)
    else:
        with CONF_FILE.open('w') as f:
            f.writelines('\n'.join(f'{tunable}={value}' for tunable, value in to_write.items()))

    cp = subprocess.run(['sysctl', '--system'])
    if cp.returncode:
        middleware.logger.error('Failed to load custom sysctl values: %d', cp.returncode)


def render(service, middleware):
    setup(middleware)
