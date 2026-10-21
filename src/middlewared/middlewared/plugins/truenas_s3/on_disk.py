"""The bucket row, kept on the bucket's own dataset.

The S3 service writes no bucket configuration on disk, so
`sharing.s3.recover` has nothing else to re-create a bucket from.

The file sits in the service's side directory: the reaper walks that
tree but acts only on directories, and the directory is 0700,
root-owned and never exported.
"""

from __future__ import annotations

import errno
import json
import os
from typing import Any

import truenas_os
from truenas_os_pyutils.io import atomic_write

__all__ = (
    "CONFIG_BACKUP",
    "CONFIG_VERSION",
    "LATCH_XATTR",
    "ROOT_XATTR",
    "SIDE_TREE",
    "bucket_layout_markers",
    "has_latch",
    "read_config_backup",
    "write_config_backup",
)

SIDE_TREE = ".truenas_s3"
SIDE_MODE = 0o700
"""The S3 service's state directory and the mode registration holds it
at. Registration refuses one owned by anyone but the daemon."""

CONFIG_BACKUP = "config_backup.json"
CONFIG_BACKUP_MODE = 0o600
CONFIG_VERSION = 1
"""A backup of any other version reads as absent: the row it would
rebuild decides who reaches the objects."""

LATCH_XATTR = "trusted.tns3_latch"
"""The S3 service's Object Lock latch, on the dataset root."""

ROOT_XATTR = "trusted.tns3_root"
"""The S3 service's root sentinel, on the dataset root of a bucket."""

RESOLVE_BENEATH_ROOT = (
    truenas_os.RESOLVE_BENEATH
    | truenas_os.RESOLVE_NO_SYMLINKS
    | truenas_os.RESOLVE_NO_MAGICLINKS
    | truenas_os.RESOLVE_NO_XDEV
)
"""The resolve flags that the S3 service uses for a name under a
dataset root. No symlinks, no other filesystems, nothing above the
root."""


def has_latch(mount: str) -> bool:
    """Whether the dataset root carries the S3 service's Object Lock
    latch. Presence is the whole test: the latch never clears, so a root
    carrying one is a locked bucket whatever the row says.

    A mount point that is not there holds no latch, which is a dataset
    that is not mounted. A record that is there and will not read is not
    a record that is not there, so every other error raises.
    """
    try:
        fd = truenas_os.openat2(mount, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return False
        raise
    try:
        truenas_os.fgetxattr(fd, LATCH_XATTR)
    except OSError as e:
        if e.errno == errno.ENODATA:
            return False
        raise
    finally:
        os.close(fd)
    return True


def bucket_layout_markers(mount: str) -> list[str]:
    """Return the parts of the S3 service's bucket layout that the
    dataset root at `mount` has. The parts are the root sentinel xattr,
    the Object Lock latch xattr, and the `.truenas_s3` directory. Return
    an empty list for a dataset that was never a bucket. This function
    only checks that each part exists. It does not read the contents.
    The service refuses a WHOLE_DATASET row if any of the three parts
    exists.

    Raise an error if `mount` cannot be opened or an xattr cannot be
    read. The directory is opened with the same flags that the service
    uses. A regular file named `.truenas_s3` does not count. A symlink
    or a mount point with that name does count, because the service's
    open fails on it.
    """
    found: list[str] = []
    fd = truenas_os.openat2(mount, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in (ROOT_XATTR, LATCH_XATTR):
            try:
                truenas_os.fgetxattr(fd, name)
            except OSError as e:
                if e.errno != errno.ENODATA:
                    raise
            else:
                found.append(name)
        try:
            side = truenas_os.openat2(
                SIDE_TREE, os.O_RDONLY | os.O_DIRECTORY | os.O_NONBLOCK, dir_fd=fd, resolve=RESOLVE_BENEATH_ROOT
            )
        except OSError as e:
            if e.errno in (errno.ENOENT, errno.ENOTDIR):
                pass
            elif e.errno in (errno.ELOOP, errno.EXDEV):
                found.append(f"{SIDE_TREE}/")
            else:
                raise
        else:
            os.close(side)
            found.append(f"{SIDE_TREE}/")
    finally:
        os.close(fd)
    return found


def backup_path(mount: str) -> str:
    return os.path.join(mount, SIDE_TREE, CONFIG_BACKUP)


def read_config_backup(mount: str) -> dict[str, Any] | None:
    """The bucket row middleware last wrote here, or None. One that does
    not parse, or that another version wrote, reads as absent."""
    try:
        with open(backup_path(mount)) as f:
            row = json.load(f)
    except FileNotFoundError:
        return None
    except ValueError:
        return None
    if not isinstance(row, dict) or row.get("version_number") != CONFIG_VERSION:
        return None
    return row


def write_config_backup(mount: str, row: dict[str, Any]) -> None:
    """Write the row into the bucket's side directory, creating it where
    registration has not. Root-owned 0700, which is what registration
    makes it and checks for."""
    side = os.path.join(mount, SIDE_TREE)
    try:
        os.mkdir(side, SIDE_MODE)
    except FileExistsError:
        pass
    else:
        # explicit: the umask applies to the mkdir mode
        os.chmod(side, SIDE_MODE)
    with atomic_write(backup_path(mount), perms=CONFIG_BACKUP_MODE) as f:
        json.dump({**row, "version_number": CONFIG_VERSION}, f)
