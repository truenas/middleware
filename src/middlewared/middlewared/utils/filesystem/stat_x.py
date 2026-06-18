# This utility provides a basic wrapper for statx(2).
#
# We need statx(2) for gathering birth time, mount id, and
# file attributes for the middleware filesystem plugin
#
# NOTE: tests for these utils are in src/middlewared/middlewared/pytest/unit/utils/test_statx.py

from enum import IntFlag, StrEnum
from pathlib import Path
import stat as statlib
from typing import Literal, TypedDict

import truenas_os

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


STATX_ATTRIBUTE = Literal['COMPRESSED', 'IMMUTABLE', 'APPEND', 'NODUMP', 'ENCRYPTED', 'AUTOMOUNT', 'MOUNT_ROOT',
                          'VERIFY', 'DAX']
STATX_DEFAULT_MASK = truenas_os.STATX_BASIC_STATS | truenas_os.STATX_BTIME | truenas_os.STATX_MNT_ID_UNIQUE


class StatxEntryResult(TypedDict, total=False):
    """Return type for statx_entry_impl"""
    st: truenas_os.StatxResult
    etype: str
    attributes: list[STATX_ATTRIBUTE]
    is_ctldir: bool  # Optional: only present if entry is absolute


def statx_entry_impl(entry: Path, dir_fd: int = truenas_os.AT_FDCWD) -> StatxEntryResult | None:
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
    path = entry.as_posix()
    try:
        # This is equivalent to lstat() call
        st = truenas_os.statx(
            path,
            dir_fd=dir_fd,
            flags=truenas_os.AT_SYMLINK_NOFOLLOW,
            mask=STATX_DEFAULT_MASK
        )
    except FileNotFoundError:
        return None

    out_st = st
    attributes: list[STATX_ATTRIBUTE] = []

    for attr in StatxAttr:
        if out_st.stx_attributes & attr.value:
            if attr.name is not None:
                attributes.append(attr.name)  # type: ignore[arg-type]

    if statlib.S_ISDIR(out_st.stx_mode):
        etype = StatxEtype.DIRECTORY.name

    elif statlib.S_ISLNK(out_st.stx_mode):
        etype = StatxEtype.SYMLINK.name
        try:
            out_st = truenas_os.statx(path, dir_fd=dir_fd, mask=STATX_DEFAULT_MASK)
        except FileNotFoundError:
            return None

    elif statlib.S_ISREG(out_st.stx_mode):
        etype = StatxEtype.FILE.name

    else:
        etype = StatxEtype.OTHER.name

    out = StatxEntryResult(st=out_st, etype=etype, attributes=attributes)

    if entry.is_absolute():
        out['is_ctldir'] = path_in_ctldir(entry)

    return out
