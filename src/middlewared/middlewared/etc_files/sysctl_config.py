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


async def render(service, middleware):
    await middleware.run_in_thread(sysctl_configuration, middleware)
