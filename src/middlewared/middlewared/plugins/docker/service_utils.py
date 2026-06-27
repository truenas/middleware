from middlewared.service import ServiceContext


async def license_active(context: ServiceContext) -> bool:
    can_run_apps = True
    if await context.middleware.call('system.is_ha_capable'):
        can_run_apps = await context.middleware.call('system.feature_enabled', 'APPS')

    return can_run_apps


async def restart_docker_service(context: ServiceContext) -> None:
    await (await context.call2(context.s.service.control, 'STOP', 'docker')).wait(raise_error=True)
    await (await context.call2(context.s.service.control, 'START', 'docker')).wait(raise_error=True)
