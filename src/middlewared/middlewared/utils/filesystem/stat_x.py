# This utility provides a basic wrapper for statx(2).
#
# We need statx(2) for gathering birth time, mount id, and
# file attributes for the middleware filesystem plugin
#
# NOTE: tests for these utils are in src/middlewared/middlewared/pytest/unit/utils/test_statx.py

import os
import ctypes
import stat as statlib
from enum import auto, Enum, IntFlag
from .constants import AT_FDCWD
from .utils import path_in_ctldir


class StatxEtype(Enum):
    DIRECTORY = auto()
    FILE = auto()
    SYMLINK = auto()
    OTHER = auto()


class ATFlags(IntFlag):
    # fcntl.h
    STATX_SYNC_AS_STAT = 0x0000
    SYMLINK_NOFOLLOW = 0x0100
    EMPTY_PATH = 0x1000
    VALID_FLAGS = 0x1100


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


class Mask(ctypes.c_uint):
    TYPE = 0x00000001  # stx_mode & S_IFMT
    MODE = 0x00000002  # stx_mode & ~S_IFMT
    NLINK = 0x00000004  # stx_nlink
    UID = 0x00000008  # stx_uid
    GID = 0x00000010  # stx_gid
    ATIME = 0x00000020  # stx_atime
    MTIME = 0x00000040  # stx_mtime
    CTIME = 0x00000080  # stx_ctime
    INO = 0x00000100  # stx_ino
    SIZE = 0x00000200  # stx_size
    BLOCKS = 0x00000400  # stx_blocks
    BASIC_STATS = 0x000007FF  # info in normal stat struct

    # Extensions
    BTIME = 0x00000800  # stx_btime
    MNT_ID = 0x00001000  # stx_mnt_id
    ALL = 0x00000FFF  # All supported flags
    _RESERVED = 0x80000000  # Reserved for future struct statx expansion


class StructStatxTimestamp(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_uint64),
        ("tv_nsec", ctypes.c_uint32),
        ("__reserved", ctypes.c_uint32),
    ]


class StructStatx(ctypes.Structure):
    _fields_ = [
        # 0x00
        ("stx_mask", Mask),
        ("stx_blksize", ctypes.c_uint32),
        ("stx_attributes", ctypes.c_uint64),

        # 0x10
        ("stx_nlink", ctypes.c_uint32),
        ("stx_uid", ctypes.c_uint32),
        ("stx_gid", ctypes.c_uint32),
        ("stx_mode", ctypes.c_uint16),
        ("__spare0", ctypes.c_uint16 * 1),

        # 0x20
        ("stx_ino", ctypes.c_uint64),
        ("stx_size", ctypes.c_uint64),
        ("stx_blocks", ctypes.c_uint64),
        ("stx_attributes_mask", ctypes.c_uint64),

        # 0x40
        ("stx_atime", StructStatxTimestamp),
        ("stx_btime", StructStatxTimestamp),
        ("stx_ctime", StructStatxTimestamp),
        ("stx_mtime", StructStatxTimestamp),

        # 0x80
        ("stx_rdev_major", ctypes.c_uint32),
        ("stx_rdev_minor", ctypes.c_uint32),
        ("stx_dev_major", ctypes.c_uint32),
        ("stx_dev_minor", ctypes.c_uint32),

        # 0x90
        ("stx_mnt_id", ctypes.c_uint64),
        ("__spare2", ctypes.c_uint64),

        # 0xa0 (Spare space)
        ("__spare3", ctypes.c_uint64 * 12),
    ]


def __get_statx_fn():
    libc = ctypes.CDLL('libc.so.6', use_errno=True)
    func = libc.statx
    func.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(StructStatx)
    )
    return func


__statx_fn = __get_statx_fn()
__statx_default_mask = int(Mask.BASIC_STATS | Mask.BTIME)
__statx_lstat_flags = int(ATFlags.STATX_SYNC_AS_STAT | ATFlags.SYMLINK_NOFOLLOW)


def statx(path, dir_fd=None, flags=ATFlags.STATX_SYNC_AS_STAT.value):
    path = path.encode() if isinstance(path, str) else path

    dir_fd = dir_fd or AT_FDCWD

    if dir_fd == AT_FDCWD and flags & ATFlags.EMPTY_PATH.value:
        raise ValueError('dir_fd is required when using AT_EMPTY_PATH')

    invalid_flags = flags & ~ATFlags.VALID_FLAGS.value
    if invalid_flags:
        raise ValueError(f'{hex(invalid_flags)}: unsupported statx flags')

    data = StructStatx()
    result = __statx_fn(dir_fd, path, flags, __statx_default_mask, ctypes.byref(data))
    if result < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    else:
        return data


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
        out['st'] = statx(
            path,
            dir_fd = dir_fd,
            flags = __statx_lstat_flags
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
            out['st'] = statx(path, dir_fd=dir_fd)
        except FileNotFoundError:
            return None

    elif statlib.S_ISREG(out['st'].stx_mode):
        out['etype'] = StatxEtype.FILE.name

    else:
        out['etype'] = StatxEtype.OTHER.name

    if entry.is_absolute():
        out['is_ctldir'] = path_in_ctldir(entry)

    return out
