from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import ServiceContext
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl


async def license_active(context: ServiceContext) -> bool:
    """
    Returns whether this system is entitled to run containers.
    """
    return (await context.call2(context.s.truenas.entitlements.check, LicenseFeature.CONTAINERS)).entitled


async def pool_choices(context: ServiceContext) -> dict[str, str]:
    pools = {}
    imported_pools = await context.to_thread(query_imported_fast_impl)
    for ds in await context.call2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(
            paths=[
                p['name']
                for p in imported_pools.values()
                if p['name'] not in BOOT_POOL_NAME_VALID
            ],
            properties=['encryption'],
        )
    ):
        enc = get_encryption_info(ds['properties'])
        if not enc.locked:
            pools[ds['name']] = ds['name']

    return pools
