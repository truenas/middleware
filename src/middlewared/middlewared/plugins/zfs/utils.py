import pathlib
from dataclasses import dataclass
from typing import Literal

import truenas_pylibzfs

from middlewared.utils import BOOT_POOL_NAME_VALID

from .exceptions import ZFSPathNotProvidedException, ZFSPathNotFoundException

__all__ = (
    "get_encryption_info",
    "group_paths_by_parents",
    "has_internal_path",
    "open_resource",
)


INTERNAL_PATHS = (
    "ix-apps",
    "ix-applications",
    ".system"
)


@dataclass(slots=True, frozen=True, kw_only=True)
class EncryptionInfo:
    encrypted: bool = False
    """Whether the zfs resource is encrypted"""
    encryption_type: Literal[None, "raw", "hex", "passphrase"] = None
    """Controls what format the user's encryption key will be provided as.
    NOTE: This property is only set when the dataset is encrypted."""
    locked: bool = False
    """Whether the zfs resource is locked"""
    location: str | None = None
    """Controls where the user's encryption key will be loaded from
    by default for commands such as zfs load-key and zfs mount -l.
    This property is only set for encrypted datasets which are
    encryption roots. If unspecified, the default is prompt.
    """


def has_internal_path(path):
    """
    Check if a ZFS resource path is an internal path.

    Internal paths include:
    - Boot pools themselves ('boot-pool', 'freenas-boot') and any dataset under them
    - System datasets directly under a data pool (e.g., 'tank/ix-apps', 'tank/.system')

    Args:
        path: A ZFS resource relative path string (e.g., 'tank/ix-apps/foo', 'boot-pool/grub')

    Returns:
        bool: True if the path represents an internal path, False otherwise
    """
    components = path.split("/")
    if components[0] in BOOT_POOL_NAME_VALID:
        return True
    return len(components) > 1 and components[1] in INTERNAL_PATHS


def get_encryption_info(data: dict) -> EncryptionInfo:
    """
    Check the various zfs properties to determine if the underlying zfs
    resource is encrypted.

    Args:
        data: dict with, minimally, the following keys to be able to
            accurately determine encryption status
            ('keystatus', 'encryption', 'keyformat', 'keylocation')

    Returns:
        dict: of keys representing the current encryption info and
            status
    """
    enc = data["encryption"]["raw"] != "off"
    if not enc:
        # no reason to continue
        return EncryptionInfo(encrypted=enc)
    else:
        return EncryptionInfo(
            encrypted=enc,
            encryption_type=data["keyformat"]["raw"],
            locked=data["keystatus"]["raw"] != "available",
            location=data["keylocation"]["raw"],
        )


def group_paths_by_parents(paths: list[str]) -> dict[str, list[str]]:
    """
    Group paths by their parent directories, mapping each parent to
    all paths that are relative to it. For each path in the input list,
    finds all other paths that are relative to that path and groups
    them together.

    Args:
        paths: List of relative POSIX path strings

    Returns:
        Dict mapping parent paths to lists of their relative subpaths.
        Empty dict if no overlapping paths exist.

    Example:
        >>> group_paths_by_parents(['dozer/test', 'dozer/test/foo', 'tank', 'dozer/abc'])
        {'dozer/test': ['dozer/test/foo']}
    """
    root_dict = dict()
    if not paths:
        return root_dict

    for path in paths:
        subpaths = list()
        for sp in paths:
            if pathlib.Path(sp).is_relative_to(pathlib.Path(path)) and sp != path:
                subpaths.append(sp)
        if subpaths:
            root_dict[path] = subpaths
    return root_dict


def open_resource(tls, path: str):
    if not path:
        raise ZFSPathNotProvidedException()

    try:
        return tls.lzh.open_resource(name=path)
    except truenas_pylibzfs.ZFSException as e:
        if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(path)
        else:
            raise e from None
