# This utility provides a basic wrapper for statx(2).
#
# We need statx(2) for gathering birth time, mount id, and
# file attributes for the middleware filesystem plugin
#
# NOTE: tests for these utils are in src/middlewared/middlewared/pytest/unit/utils/test_statx.py

import os
import stat as statlib
import truenas_os
from enum import IntFlag, StrEnum
from .utils import path_in_ctldir


class StatxEtype(StrEnum):
    DIRECTORY = 'DIRECTORY'
    FILE = 'FILE'
    SYMLINK = 'SYMLINK'
    OTHER = 'OTHER'


class StatxAttr(IntFlag):
    # uapi/linux/stat.h
    COMPRESSED = 0x00000004
    IMMUTABLE = 0x00000010
    APPEND = 0x00000020
    NODUMP = 0x00000040
    ENCRYPTED = 0x00000800
    AUTOMOUNT = 0x00001000
    MOUNT_ROOT = 0x00002000
    VERIFY = 0x00100000
    DAX = 0x00200000


STATX_DEFAULT_MASK = truenas_os.STATX_BASIC_STATS | truenas_os.STATX_BTIME | truenas_os.STATX_MNT_ID_UNIQUE


def statx_entry_impl(entry, dir_fd=None, get_ctldir=True):
    """
    This is a convenience wrapper around stat_x that was originally
    located within the filesystem plugin

    `entry` - pathlib.Path for target of statx

    returns a dictionary with the following keys:
    `st` - StructStatx object for entry

    `attributes` - statx attributes

    `etype` - file type (matches names in FileType enum)

    `is_ctldir` - boolean value indicating whether path is in the
    ZFS ctldir. NOTE: is_ctldir is omitted when using a relative path

    Warning: this method is blocking and includes data that is not JSON
    serializable
    """
    out = {'st': None, 'etype': None, 'attributes': []}

    path = entry.as_posix()
    try:
        # This is equivalent to lstat() call
        out['st'] = truenas_os.statx(
            path,
            dir_fd=dir_fd or truenas_os.AT_FDCWD,
            flags=truenas_os.AT_SYMLINK_NOFOLLOW,
            mask=STATX_DEFAULT_MASK
        )
    except FileNotFoundError:
        return None

    for attr in StatxAttr:
        if out['st'].stx_attributes & attr.value:
            out['attributes'].append(attr.name)

    if statlib.S_ISDIR(out['st'].stx_mode):
        out['etype'] = StatxEtype.DIRECTORY.name

    elif statlib.S_ISLNK(out['st'].stx_mode):
        out['etype'] = StatxEtype.SYMLINK.name
        try:
            out['st'] = truenas_os.statx(path, dir_fd=dir_fd, mask=STATX_DEFAULT_MASK)
        except FileNotFoundError:
            return None

    elif statlib.S_ISREG(out['st'].stx_mode):
        out['etype'] = StatxEtype.FILE.name

    else:
        out['etype'] = StatxEtype.OTHER.name

    if entry.is_absolute():
        out['is_ctldir'] = path_in_ctldir(entry)

    return out
