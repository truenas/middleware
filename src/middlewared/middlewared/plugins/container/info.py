from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.truenas.license_utils import FeaturePolicy
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import ServiceContext
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl


async def license_active(context: ServiceContext) -> bool:
    """
    If this is iX enterprise hardware and has NOT been licensed to run containers
    then this will return False, otherwise this will return true.
    """
    available: bool = await context.middleware.call(
        'truenas.license.feature_available', 'APPS', FeaturePolicy.IX_HARDWARE
    )
    return available


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
