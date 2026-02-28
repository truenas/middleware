from ixhardware.chassis import TRUENAS_UNKNOWN

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import ServiceContext
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl


async def license_active(context: ServiceContext) -> bool:
    """
    If this is iX enterprise hardware and has NOT been licensed to run containers
    then this will return False, otherwise this will return true.
    """
    system_chassis = await context.call2(context.s.truenas.get_chassis_hardware)
    if system_chassis == TRUENAS_UNKNOWN or 'MINI' in system_chassis:
        # 1. if it's not iX branded hardware
        # 2. OR if it's a MINI, then allow containers/vms
        return True

    license_ = await context.middleware.call('system.license')
    if license_ is None:
        # it's iX branded hardware but has no license
        return False

    return 'JAILS' in license_['features']


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
