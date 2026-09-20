from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
import errno
import pathlib
from typing import TYPE_CHECKING, Any, Literal

import truenas_pylibzfs

from middlewared.service_exception import ValidationError
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID

from .exceptions import ZFSPathNotFoundException, ZFSPathNotProvidedException

if TYPE_CHECKING:
    from middlewared.api.current import ZfsTierEntry
    from middlewared.main import Middleware
    from middlewared.service import ServiceContext

__all__ = (
    "get_encryption_info",
    "group_paths_by_parents",
    "has_internal_path",
    "open_resource",
    "pool_has_special_vdev",
    "pool_is_draid",
    "reject_overlapping_paths",
    "reject_protected_path",
    "reject_snapshot_path",
    "special_vdev_thresholds",
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


def has_internal_path(path: str) -> bool:
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


def get_encryption_info(data: dict[str, dict[str, Any]]) -> EncryptionInfo:
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


def pool_is_draid(context: ServiceContext, pool_name: str) -> bool:
    if pool := context.middleware.call_sync("zpool.query_impl", {"pool_names": [pool_name], "topology": True}):
        for group in pool[0]["topology"]["data"] + pool[0]["topology"].get("special", []):
            if group["vdev_type"].startswith("draid"):
                return True
    return False


async def pool_has_special_vdev(middleware: Middleware, pool_name: str) -> bool:
    """False when the pool cannot be inspected."""
    try:
        pools = await middleware.call(
            "zpool.query_impl",
            {"pool_names": [pool_name], "properties": ["class_special_size"]},
        )
        if not pools:
            return False
        special_size = ((pools[0].get("properties") or {}).get("class_special_size") or {}).get("value")
    except Exception:
        middleware.logger.debug("%s: failed to query pool SPECIAL vdev size", pool_name, exc_info=True)
        return False
    return isinstance(special_size, int) and special_size > 0


def group_paths_by_parents(paths: Collection[str]) -> dict[str, list[str]]:
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
    root_dict: dict[str, list[str]] = dict()
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


def reject_protected_path(schema: str, path: str, bypass: bool = False) -> None:
    """Raise if ``path`` is an internal path and the caller may not touch it.

    A snapshot inherits the protection status of the dataset it belongs to.
    ``bypass`` is only exposed to internal callers, never to the public API.
    """
    if not bypass and has_internal_path(path.split("@", 1)[0]):
        raise ValidationError(schema, f"{path!r} is a protected path.", errno.EACCES)


def reject_snapshot_path(schema: str, path: str) -> None:
    if "@" in path:
        raise ValidationError(
            schema,
            "Snapshot paths are not accepted. Use the `zfs.resource.snapshot` methods to manage snapshots.",
            errno.EINVAL,
        )


def reject_overlapping_paths(schema: str, paths: Collection[str], option: str) -> None:
    """Raise if any path is relative to another. A recursive walk must not overlap."""
    if group_paths_by_parents(paths):
        raise ValidationError(
            schema,
            f"Paths must be non-overlapping - no path can be relative to another when {option} is set.",
        )


def open_resource(tls: Any, path: str) -> Any:
    if not path:
        raise ZFSPathNotProvidedException()

    try:
        return tls.lzh.open_resource(name=path)
    except truenas_pylibzfs.ZFSException as e:
        if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(path)
        else:
            raise e from None


def special_vdev_thresholds(config: ZfsTierEntry) -> tuple[int, int]:
    """Return ``(warning, critical)`` SPECIAL-vdev fill thresholds in percent.

    ``critical`` is the lower of the user's configured cap
    (``max_used_percentage``) and the actual ZFS overflow point
    (``100 - special_class_metadata_reserve_pct``) — beyond which the
    kernel stops sending small blocks to SPECIAL and spills them to
    NORMAL, so letting the user set the cap higher than that is
    meaningless.

    ``warning`` sits 10 points below critical with a floor of 50% so the
    warning stays useful even at the minimum cap settings.
    """
    critical = min(
        config.max_used_percentage,
        100 - config.special_class_metadata_reserve_pct,
    )
    warning = max(critical - 10, 50)
    return warning, critical
