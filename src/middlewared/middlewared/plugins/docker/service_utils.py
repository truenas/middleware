from middlewared.plugins.truenas.license_utils import FeaturePolicy
from middlewared.service import ServiceContext


async def license_active(context: ServiceContext) -> bool:
    available: bool = await context.middleware.call(
        'truenas.license.feature_available', 'APPS', FeaturePolicy.HA_APPLIANCE
    )
    return available


async def restart_docker_service(context: ServiceContext) -> None:
    await (await context.middleware.call('service.control', 'STOP', 'docker')).wait(raise_error=True)
    await (await context.middleware.call('service.control', 'START', 'docker')).wait(raise_error=True)
