import subprocess

from middlewared.plugins.tunables import TUNABLES_DEFAULT_FILE


def sysctl_configuration(middleware):
    tuneables = middleware.call_sync('tunable.query', [
        ['enabled', '=', True], ['type', '=', 'SYSCTL']
    ])
    for tuneable in tuneables:
        ret = subprocess.run(
            ['sysctl', f'{tuneable["var"]}="{tuneable["value"]}"'],
            capture_output=True
        )
        if ret.returncode:
            middleware.logger.debug(
                'Failed to set sysctl %s -> %s: %s',
                tuneable['var'], tuneable['value'], ret.stderr.decode(),
            )
    tuneables = middleware.call_sync('tunable.query', [
        ['enabled', '=', False], ['type', '=', 'SYSCTL']
    ])
    if len(tuneables) > 0:
        # Read from file
        default_sysctl = {}
        try:
            with open(TUNABLES_DEFAULT_FILE, 'r') as f:
                for line in f.readlines():
                    line = line.rstrip()
                    groups = line.split(" = ")
                    default_sysctl[groups[0]] = groups[1]
        except Exception:
            pass
        for tuneable in tuneables:
            middleware.logger.debug(f'{tuneable["var"]}="{default_sysctl[tuneable["var"]]}"')
            if tuneable['var'] in default_sysctl.keys():
                ret = subprocess.run(
                    ['sysctl', f'{tuneable["var"]}="{default_sysctl[tuneable["var"]]}"'],
                    capture_output=True
                )
                if ret.returncode:
                    middleware.logger.debug(
                        'Failed to set sysctl %s -> %s: %s',
                        tuneable['var'], tuneable['value'], ret.stderr.decode(),
                    )


def render(service, middleware):
    sysctl_configuration(middleware)
