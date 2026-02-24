from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


async def recommended_zvol_blocksize_impl(ctx: ServiceContext, pool: str) -> str:
    pool_obj = await ctx.middleware.call('pool.query', [['name', '=', pool]], {'get': True})

    """
    Cheatsheat for blocksizes is as follows:
    2w/3w mirror = 16K
    3wZ1, 4wZ2, 5wZ3 = 16K
    4w/5wZ1, 5w/6wZ2, 6w/7wZ3 = 32K
    6w/7w/8w/9wZ1, 7w/8w/9w/10wZ2, 8w/9w/10w/11wZ3 = 64K
    10w+Z1, 11w+Z2, 12w+Z3 = 128K

    If the zpool was forcefully created with mismatched
    vdev geometry (i.e. 3wZ1 and a 5wZ1) then we calculate
    the blocksize based on the largest vdev of the zpool.
    """
    maxdisks = 1
    for vdev in pool_obj['topology']['data']:
        if vdev['type'] == 'RAIDZ1':
            disks = len(vdev['children']) - 1
        elif vdev['type'] == 'RAIDZ2':
            disks = len(vdev['children']) - 2
        elif vdev['type'] == 'RAIDZ3':
            disks = len(vdev['children']) - 3
        elif vdev['type'] == 'MIRROR':
            disks = maxdisks
        else:
            disks = len(vdev['children'])

        if disks > maxdisks:
            maxdisks = disks

    return f'{max(16, min(128, 2 ** ((maxdisks * 8) - 1).bit_length()))}K'
