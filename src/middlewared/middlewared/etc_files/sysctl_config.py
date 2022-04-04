from middlewared.utils import run


async def sysctl_configuration(middleware):
    sysdefs = await middleware.call('tunable.get_system_defaults')
    for tun in filter(lambda x: x in sysdefs, (await middleware.call('tunable.query', [['type', '=', 'SYSCTL']]))):
        value_default = sysdefs[tun['var']]
        if tun['enabled']:
            if not value_default:
                cp = await run(['sysctl', tun['var']], check=False, encoding='utf8')
                if cp.returncode:
                    middleware.logger.error(
                        'Failed to get default value of %r : %s', tun['var'], cp.stderr.strip()
                    )
                else:
                    value_default = sysdefs[tun['var']] = cp.stdout.split('=')[-1].strip()
                    await middleware.call('tunable.set_default_value', tun['var'], value_default)
            cp = await run(['sysctl', f'{tun["var"]}={tun["value"]}'], check=False, encoding='utf8')
            if cp.returncode:
                middleware.logger.error(
                    'Failed to set sysctl %r -> %r : %s', tun['var'], tun['value'], cp.stderr.strip()
                )
        elif value_default:
            cp = await run(['sysctl', f'{tun["var"]}={value_default}'], check=False, encoding='utf8')
            if cp.returncode:
                middleware.logger.error(
                    'Failed to set sysctl %r -> %r : %s', tun['var'], tun['value'], cp.stderr.strip()
                )


async def render(service, middleware):
    await sysctl_configuration(middleware)
