from middlewared.utils import osc, run


async def sysctl_configuration(middleware):
    default_sysctl_config = await middleware.call('tunable.default_sysctl_config')
    for tunable in await middleware.call('tunable.query', [['type', '=', 'SYSCTL']]):
        value_default = default_sysctl_config.get(tunable['var'])
        if tunable['enabled']:
            if not value_default:
                cp = await run(['sysctl', tunable['var']], check=False, encoding='utf8')
                if cp.returncode:
                    middleware.logger.error(
                        'Failed to get default value of %r : %s', tunable['var'], cp.stderr.strip()
                    )
                else:
                    value_default = default_sysctl_config[tunable['var']] = cp.stdout.split(
                        '=' if osc.IS_LINUX else ':'
                    )[-1].strip()
                    await middleware.call('tunable.set_default_value', tunable['var'], value_default)
            cp = await run(['sysctl', f'{tunable["var"]}={tunable["value"]}'], check=False, encoding='utf8')
            if cp.returncode:
                middleware.logger.error(
                    'Failed to set sysctl %r -> %r : %s', tunable['var'], tunable['value'], cp.stderr.strip()
                )
        elif value_default:
            cp = await run(['sysctl', f'{tunable["var"]}={value_default}'], check=False, encoding='utf8')
            if cp.returncode:
                middleware.logger.error(
                    'Failed to set sysctl %r -> %r : %s', tunable['var'], tunable['value'], cp.stderr.strip()
                )


async def render(service, middleware):
    await sysctl_configuration(middleware)
