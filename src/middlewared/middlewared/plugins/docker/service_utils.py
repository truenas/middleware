from middlewared.service import ServiceContext


async def license_active(context: ServiceContext) -> bool:
    can_run_apps = True
    if await context.middleware.call('system.is_ha_capable'):
        license_ = await context.middleware.call('system.license')
        can_run_apps = license_ is not None and 'JAILS' in license_['features']

    return can_run_apps


async def restart_docker_service(context: ServiceContext) -> None:
    await (await context.middleware.call('service.control', 'STOP', 'docker')).wait(raise_error=True)
    await (await context.middleware.call('service.control', 'START', 'docker')).wait(raise_error=True)
