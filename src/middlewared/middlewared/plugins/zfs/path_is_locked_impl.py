from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from truenas_pylibzfs import ZFSError, ZFSException, ZFSType

from .zvol_utils import zvol_path_to_name

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("path_is_locked_impl",)


def _covered(about_to_lock: str | None, name: str) -> bool:
    return bool(about_to_lock) and (name == about_to_lock or name.startswith(f"{about_to_lock}/"))


def _locked(tls: Any, name: str, about_to_lock: str | None, authoritative: bool) -> bool:
    try:
        rsrc = tls.lzh.open_resource(name=name)
        if rsrc.type == ZFSType.ZFS_TYPE_SNAPSHOT:
            dataset = name.partition("@")[0]
            rsrc = tls.lzh.open_resource(name=dataset)
            # Under /mnt a filesystem snapshot is never meant (it mounts under .zfs), so only a zvol snapshot counts.
            if not authoritative and rsrc.type != ZFSType.ZFS_TYPE_VOLUME:
                return False
            if _covered(about_to_lock, dataset):
                return True
    except ZFSException as e:
        if e.code in (ZFSError.EZFS_NOENT, ZFSError.EZFS_INVALIDNAME):
            return False
        raise

    crypto = rsrc.crypto()
    return crypto is not None and not crypto.info().key_is_loaded


def path_is_locked_impl(context: ServiceContext, tls: Any, path: str) -> bool:
    # WARNING: _EXTREMELY_ hot code path. Do not add more
    # things here unless you fully understand the side-effects.
    path_authoritative = True
    if path.startswith("/dev/zvol/"):
        path = zvol_path_to_name(path)
    elif os.path.isabs(path):
        path = path.removeprefix("/mnt/")
        path_authoritative = False
    path = path.removesuffix("/")

    try:
        about_to_lock: str | None = context.middleware.call_sync("cache.get", "about_to_lock_dataset")
    except KeyError:
        about_to_lock = None
    # A dataset whose services are being stopped ahead of a lock reads as locked before its key is unloaded.
    if _covered(about_to_lock, path):
        return True

    if path_authoritative:
        return _locked(tls, path, about_to_lock, True)

    if _locked(tls, path, about_to_lock, False):
        return True
    # The mount tree never passes through a snapshot, so a parent containing "@" is a directory.
    return any(
        _locked(tls, p.as_posix(), about_to_lock, False) for p in Path(path).parents[:-1] if "@" not in p.as_posix()
    )
