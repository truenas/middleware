from __future__ import annotations

import errno
from typing import TYPE_CHECKING

from middlewared.service_exception import ValidationError

from .property_choices import ZFS_CHECKSUM_CHOICES, ZFS_COMPRESSION_ALGORITHM_CHOICES
from .property_choices import recommended_zvol_blocksize as _recommended_zvol_blocksize
from .property_choices import recordsize_choices as _recordsize_choices
from .utils import pool_is_draid

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
    draid = False
    if pool_name:
        draid = pool_is_draid(context, pool_name)
    with open(ZFS_MAX_RECORDSIZE) as f:
        return _recordsize_choices(int(f.read().strip()), draid)


def recommended_zvol_blocksize(context: ServiceContext, pool: str) -> str:
    entries = context.middleware.call_sync("zpool.query_impl", {"pool_names": [pool], "topology": True})
    if not entries:
        raise ValidationError("zfs.resource.recommended_zvol_blocksize.pool", f"{pool!r} does not exist", errno.ENOENT)
    return _recommended_zvol_blocksize(entries[0]["topology"]["data"])
