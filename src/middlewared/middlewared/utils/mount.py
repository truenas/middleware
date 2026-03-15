# NOTE: iter_mountinfo, statmount, umount, and related types were previously defined
# here and have been moved to truenas_os_pyutils:
# https://github.com/truenas/truenas_pyos/tree/master/src/truenas_os_pyutils
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import truenas_os

if TYPE_CHECKING:
    from middlewared.main import Middleware

logger = logging.getLogger(__name__)

__all__ = ["resolve_dataset_path"]


def resolve_dataset_path(path: str, middleware: Middleware | None = None) -> tuple[str, str] | tuple[None, None]:
    """
    Authoritatively resolve a filesystem path to its ZFS dataset and relative path.

    This function determines which ZFS dataset contains a given path using a multi-level
    approach that handles both mounted and unmounted datasets:

    1. **Mounted paths**: Uses statx + statmount to get mount information from the kernel
    2. **Unmounted dataset placeholders**: Uses statx IMMUTABLE attribute + libzfs lookup
    3. **Unresolvable paths**: Returns (None, None) for paths that can't be resolved yet

    Common reasons for unresolvable paths:
    - Encrypted dataset not yet unlocked
    - Hardware issues (disk offline, pool degraded)
    - Path doesn't exist (will be created later)
    - Permission issues preventing stat

    Args:
        path: Absolute filesystem path to resolve (e.g., '/mnt/tank/share/data')
        middleware: Middleware instance (required for libzfs lookup of unmounted datasets)

    Returns:
        ('pool/dataset', 'relative/path') if successfully resolved
        (None, None) if path cannot be resolved yet
    """
    try:
        # Get file stats with mount ID and attributes
        path = os.path.normpath(path)
        fd = truenas_os.openat2(path, os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
        try:
            stx = truenas_os.statx(
                "",
                dir_fd=fd,
                flags=truenas_os.AT_EMPTY_PATH,
                mask=truenas_os.STATX_BASIC_STATS | truenas_os.STATX_MNT_ID_UNIQUE
            )
        finally:
            os.close(fd)
    except FileNotFoundError:
        # Path doesn't exist - likely encrypted dataset or temporarily unavailable
        logger.debug(f"Path not found (deferred): {path}")
        return None, None
    except Exception as e:
        logger.debug(f"statx failed for {path}: {e}")
        return None, None

    # Extract attributes
    is_mountroot = bool(stx.stx_attributes & truenas_os.STATX_ATTR_MOUNT_ROOT)
    is_immutable = bool(stx.stx_attributes & truenas_os.STATX_ATTR_IMMUTABLE)

    # Case 1: Mounted and accessible
    if not is_immutable:
        try:
            mntinfo = truenas_os.statmount(
                stx.stx_mnt_id,
                mask=(
                    truenas_os.STATMOUNT_SB_BASIC |
                    truenas_os.STATMOUNT_MNT_POINT |
                    truenas_os.STATMOUNT_FS_TYPE |
                    truenas_os.STATMOUNT_SB_SOURCE
                )
            )

            # Verify it has sb_source (ZFS datasets will have this)
            if mntinfo.sb_source and mntinfo.mnt_point:
                dataset = mntinfo.sb_source
                relative_path = os.path.relpath(path, mntinfo.mnt_point)
                if relative_path == '.':
                    relative_path = ''

                return dataset, relative_path
        except Exception as e:
            logger.debug(f"statmount failed for {path}: {e}")

    # Case 2: Immutable mountpoint (unmounted dataset with placeholder directory)
    # This handles ZFS datasets that create immutable directories when unmounted
    if is_mountroot and is_immutable:
        if middleware is None:
            return None, None

        try:
            # Use libzfs via middleware to look up dataset by mountpoint
            datasets = middleware.call_sync('pool.dataset.query', [['mountpoint', '=', path]])
            if datasets:
                dataset_name = datasets[0]['id']
                return dataset_name, ''
        except Exception as e:
            logger.debug(f"libzfs lookup failed for {path}: {e}")

    # Case 3: Cannot authoritatively resolve - defer for later
    # This includes: encrypted datasets not yet unlocked, hardware issues, etc.
    return None, None
