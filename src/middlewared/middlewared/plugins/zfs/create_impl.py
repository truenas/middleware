from typing import Any, Literal

import truenas_pylibzfs

from .exceptions import ZFSPathAlreadyExistsException, ZFSPathNotFoundException
from .mount_unmount_impl import mount_impl

__all__ = (
    "ZFS_TYPE_MAP",
    "create_ancestors",
    "create_leaf",
)

ZFS_TYPE_MAP = {
    "FILESYSTEM": truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
    "VOLUME": truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME,
}

def _create_one(
    tls: Any,
    name: str,
    ztype: Any,
    properties: dict[str, str | int] | None = None,
    user_properties: dict[str, str] | None = None,
    crypto: Any = None,
) -> None:
    kwargs: dict[str, Any] = {"name": name, "type": ztype}
    if properties:
        kwargs["properties"] = properties
    if user_properties:
        kwargs["user_properties"] = user_properties
    if crypto:
        kwargs["crypto"] = crypto
    try:
        tls.lzh.create_resource(**kwargs)
    except truenas_pylibzfs.ZFSException as e:
        if e.code == truenas_pylibzfs.ZFSError.EZFS_EXISTS:
            raise ZFSPathAlreadyExistsException(name)
        elif e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            # the parent is what does not exist
            raise ZFSPathNotFoundException(name.rsplit("/", 1)[0])
        raise


def create_ancestors(tls: Any, missing: list[str], mount: bool) -> list[str]:
    """
    Create the missing ancestor filesystems of a resource, outermost first, and return the names created.

    Raises:
        ZFSPathNotFoundException: the pool itself does not exist.
        truenas_pylibzfs.ZFSException: any other libzfs failure.
    """
    created = []
    for pp in missing:
        try:
            _create_one(tls, pp, truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM)
        except ZFSPathAlreadyExistsException:
            continue
        if mount:
            mount_impl(tls, pp, None, False, None, False, False)
        created.append(pp)
    return created


def create_leaf(
    tls: Any,
    path: str,
    type_: Literal["FILESYSTEM", "VOLUME"],
    properties: dict[str, str | int],
    user_properties: dict[str, str],
    crypto: Any,
) -> None:
    _create_one(tls, path, ZFS_TYPE_MAP[type_], properties, user_properties, crypto)
