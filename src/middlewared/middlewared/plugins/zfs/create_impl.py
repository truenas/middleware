import pathlib
from typing import Any, Literal

import truenas_pylibzfs

from .exceptions import ZFSPathAlreadyExistsException, ZFSPathNotFoundException
from .mount_unmount_impl import mount_impl

__all__ = (
    "ZFS_INVALID_INPUT_ERRORS",
    "ZFS_TYPE_MAP",
    "create_impl",
)

ZFS_TYPE_MAP = {
    "FILESYSTEM": truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
    "VOLUME": truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME,
}

ZFS_INVALID_INPUT_ERRORS = frozenset(
    {
        truenas_pylibzfs.ZFSError.EZFS_BADPROP,
        truenas_pylibzfs.ZFSError.EZFS_BADTYPE,
        truenas_pylibzfs.ZFSError.EZFS_INVALIDNAME,
        truenas_pylibzfs.ZFSError.EZFS_NAMETOOLONG,
        truenas_pylibzfs.ZFSError.EZFS_PROPNONINHERIT,
        truenas_pylibzfs.ZFSError.EZFS_PROPREADONLY,
        truenas_pylibzfs.ZFSError.EZFS_PROPSPACE,
        truenas_pylibzfs.ZFSError.EZFS_PROPTYPE,
        truenas_pylibzfs.ZFSError.EZFS_VOLTOOBIG,
    }
)
"""ZFSException codes from a create that mean the caller's input was the
problem (bad property name/value/type, bad name) rather than an
operational failure."""


def _create_one(
    tls: Any,
    name: str,
    ztype: Any,
    properties: dict[str, str | int] | None = None,
    user_properties: dict[str, str] | None = None,
    encrypt: dict[str, Any] | None = None,
) -> None:
    kwargs: dict[str, Any] = {"name": name, "type": ztype}
    if properties:
        kwargs["properties"] = properties
    if user_properties:
        kwargs["user_properties"] = user_properties
    if encrypt:
        try:
            kwargs["crypto"] = tls.lzh.resource_cryptography_config(
                keyformat=encrypt["keyformat"],
                key=encrypt["key"],
                pbkdf2iters=encrypt.get("pbkdf2iters"),
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid encryption configuration: {e}") from None
    try:
        tls.lzh.create_resource(**kwargs)
    except truenas_pylibzfs.ZFSException as e:
        if e.code == truenas_pylibzfs.ZFSError.EZFS_EXISTS:
            raise ZFSPathAlreadyExistsException(name)
        elif e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            # the parent is what does not exist
            raise ZFSPathNotFoundException(name.rsplit("/", 1)[0])
        raise


def _should_mount(properties: dict[str, str | int]) -> bool:
    return properties.get("mountpoint") not in ("legacy", "none") and properties.get("canmount", "on") == "on"


def create_impl(
    tls: Any,
    path: str,
    type_: Literal["FILESYSTEM", "VOLUME"],
    properties: dict[str, str | int],
    user_properties: dict[str, str],
    create_ancestors: bool,
    encrypt: dict[str, Any] | None = None,
) -> None:
    """
    Create a ZFS resource (filesystem or volume) and mount it.

    Args:
        path: The path of the zfs resource to create ('pool/name' form).
        type_: The type of resource to create.
        properties: ZFS properties to set at creation time, keyed by
            native ZFS property name.
        user_properties: ZFS user properties to set at creation time.
        create_ancestors: Create any missing ancestor filesystems first
            (like `zfs create -p`). Ancestors that already exist are
            left untouched. Ancestors are always created unencrypted /
            inheriting - `encrypt` applies to `path` only.
        encrypt: Make `path` a new encryption root. A dict with
            'keyformat' ('hex' or 'passphrase'), 'key' (the key material),
            and optionally 'pbkdf2iters'. The key material travels to ZFS
            through an in-memory key file, never through the property list.

    Raises:
        ZFSPathAlreadyExistsException: `path` already exists.
        ZFSPathNotFoundException: the parent of `path` does not exist, or,
            with `create_ancestors`, the pool itself does not.
        truenas_pylibzfs.ZFSException: any other libzfs failure.
    """
    created_ancestors = []
    if create_ancestors:
        for parent in reversed(pathlib.PurePosixPath(path).parents):
            pp = parent.as_posix()
            if "/" not in pp:
                # "." (no parent) or the pool's root filesystem
                continue
            try:
                _create_one(tls, pp, truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM)
            except ZFSPathAlreadyExistsException:
                continue
            created_ancestors.append(pp)

    _create_one(tls, path, ZFS_TYPE_MAP[type_], properties, user_properties, encrypt)

    # `zfs create` mounts what it creates; libzfs itself does not, so
    # mirror the CLI behavior here.
    for ancestor in created_ancestors:
        mount_impl(tls, ancestor, None, False, None, False, False)
    if type_ == "FILESYSTEM" and _should_mount(properties):
        mount_impl(tls, path, None, False, None, False, False)
