from __future__ import annotations

from typing import TYPE_CHECKING

from .property_choices import ZFS_CHECKSUM_CHOICES, ZFS_COMPRESSION_ALGORITHM_CHOICES
from .property_choices import recommended_zvol_blocksize as _recommended_zvol_blocksize
from .property_choices import recordsize_choices as _recordsize_choices

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = (
    "checksum_choices",
    "compression_choices",
    "recommended_zvol_blocksize",
    "recordsize_choices",
)

ZFS_MAX_RECORDSIZE = "/sys/module/zfs/parameters/zfs_max_recordsize"


def checksum_choices() -> dict[str, str]:
    return {v: v for v in ZFS_CHECKSUM_CHOICES if v != "OFF"}


def compression_choices() -> dict[str, str]:
    return {v: v for v in ZFS_COMPRESSION_ALGORITHM_CHOICES}


def recordsize_choices(context: ServiceContext, pool_name: str | None) -> list[str]:
    draid = bool(pool_name) and context.middleware.call_sync("pool.is_draid_pool", pool_name)
    with open(ZFS_MAX_RECORDSIZE) as f:
        return _recordsize_choices(int(f.read().strip()), draid)


async def recommended_zvol_blocksize(context: ServiceContext, pool: str) -> str:
    entry = await context.middleware.call("pool.query", [["name", "=", pool]], {"get": True})
    return _recommended_zvol_blocksize(entry["topology"]["data"])
