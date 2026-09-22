from typing import Annotated, Any

from pydantic import BeforeValidator

from middlewared.utils.size import zfs_size_bytes

__all__ = ["ZFSSize", "ZFSSpaceLimit"]


def _space_limit(value: Any) -> int:
    if value == "none":
        return 0
    return zfs_size_bytes(value)


ZFSSize = Annotated[int, BeforeValidator(zfs_size_bytes)]
ZFSSpaceLimit = Annotated[int, BeforeValidator(_space_limit)]
