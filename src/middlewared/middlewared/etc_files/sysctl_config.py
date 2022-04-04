from middlewared.utils import run


async def sysctl_configuration(middleware):
    sysdefs = await middleware.call('tunable.get_system_defaults')
    for tun in filter(lambda x: x in sysdefs, (await middleware.call('tunable.query', [['type', '=', 'SYSCTL']]))):
        if tun['enabled'] and (sysdefs[tun['var']] != tun['value']):
            # tunable is enabled and the variable's value set by the end-user doesn't match what the system's
            # default value is so change it
            cp = await run(['sysctl', f'{tun["var"]}={tun["value"]}'], check=False, encoding='utf8')
            if cp.returncode:
                middleware.logger.error(
                    'Failed to set sysctl %r -> %r : %s', tun['var'], tun['value'], cp.stderr.strip()
                )


async def render(service, middleware):
    await sysctl_configuration(middleware)
