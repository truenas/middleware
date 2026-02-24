from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

# https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Module%20Parameters.html#zfs-max-recordsize
# Maximum supported (at time of writing) is 16MB.
RECORDSIZE_MAPPING = [
    (1 << 9, '512'),
    (1 << 9, '512B'),
    (1 << 10, '1K'),
    (1 << 11, '2K'),
    (1 << 12, '4K'),
    (1 << 13, '8K'),
    (1 << 14, '16K'),
    (1 << 15, '32K'),
    (1 << 16, '64K'),
    (1 << 17, '128K'),
    (1 << 18, '256K'),
    (1 << 19, '512K'),
    (1 << 20, '1M'),
    (1 << 21, '2M'),
    (1 << 22, '4M'),
    (1 << 23, '8M'),
    (1 << 24, '16M'),
]


def recordsize_choices_impl(ctx: ServiceContext, pool_name: str | None) -> list[str]:
    minimum_recordsize = RECORDSIZE_MAPPING[0][0]
    if pool_name and ctx.middleware.call_sync('pool.is_draid_pool', pool_name):
        minimum_recordsize = 1 << 17  # We want minimum of 128k for dRAID pools

    with open('/sys/module/zfs/parameters/zfs_max_recordsize') as f:
        val = int(f.read().strip())
        return [v for k, v in RECORDSIZE_MAPPING if minimum_recordsize <= k <= val]
