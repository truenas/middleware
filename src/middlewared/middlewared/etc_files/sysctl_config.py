import subprocess


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
        for tuneable in tuneables:
            value_default = None
            try:
                value_default = middleware.call_sync('tunable.get_default_value', tuneable["var"])
            except KeyError:
                pass
            if value_default is not None:
                ret = subprocess.run(
                    ['sysctl', f'{tuneable["var"]}="{value_default}"'],
                    capture_output=True
                )
                if ret.returncode:
                    middleware.logger.debug(
                        'Failed to set sysctl %s -> %s: %s',
                        tuneable['var'], tuneable['value'], ret.stderr.decode(),
                    )


def render(service, middleware):
    sysctl_configuration(middleware)
