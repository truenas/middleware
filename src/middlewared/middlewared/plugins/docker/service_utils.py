from truenas_pylicensed.features import LicenseFeature

from middlewared.service import ServiceContext


async def license_active(context: ServiceContext) -> bool:
    return (await context.call2(context.s.truenas.entitlements.check, LicenseFeature.APPS)).entitled


async def restart_docker_service(context: ServiceContext) -> None:
    await (await context.call2(context.s.service.control, 'STOP', 'docker')).wait(raise_error=True)
    await (await context.call2(context.s.service.control, 'START', 'docker')).wait(raise_error=True)
