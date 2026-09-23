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
    "SIDE_TREE",
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
