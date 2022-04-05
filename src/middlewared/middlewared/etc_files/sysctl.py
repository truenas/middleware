from pathlib import Path

CONF_FILE = Path('/etc/sysctl.d/tunables.conf')


def setup(middleware):
    to_write = {}
    for tun in middleware.call_sync('tunable.query', [['type', '=', 'SYSCTL']]):
        if tun['enabled']:
            # tunable is enabled and the variable's value set by the end-user doesn't match what the system's
            # default value is so change it
            to_write[tun['var']] = tun['value']
        elif tun['orig_value']:
            # tunable is disabled and we have an original value before it was created so update
            to_write[tun['var']] = tun['orig_value']

    if not to_write:
        # no tunables or all disabled so make sure the config file is removed
        CONF_FILE.unlink(missing_ok=True)
    else:
        with CONF_FILE.open('w') as f:
            f.writelines('\n'.join(f'{tunable}={value}' for tunable, value in to_write.items()))


def render(service, middleware):
    setup(middleware)
