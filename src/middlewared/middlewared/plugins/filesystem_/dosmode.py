import fcntl
import os
import stat
import struct

from middlewared.service import CallError
from middlewared.utils.path import pathref_reopen
from enum import IntFlag


ZFS_IOC_GETDOSFLAGS = 0x80088301
ZFS_IOC_SETDOSFLAGS = 0x40088302


class DOSFlag(IntFlag):
    READONLY = 0x0000000100000000
    HIDDEN = 0x0000000200000000
    SYSTEM = 0x0000000400000000
    ARCHIVE = 0x0000000800000000
    REPARSE = 0x0000080000000000
    OFFLINE = 0x0000100000000000
    SPARSE = 0x0000200000000000
    ALL = 0x0000380f00000000

    def flags_to_dict(flags: int) -> dict:
        out = {}
        for f in DOSFlag:
            if f == DOSFlag.ALL:
                continue

            out[f.name.lower()] = True if flags & f else False

        return out

    def dict_to_flags(flags: dict) -> int:
        out = 0
        for flag, enabled in flags.items():
            if not enabled:
                continue

            out |= DOSFlag[flag.upper()]

        return out


def get_dosflags(path: str) -> dict:
    o_path_fd = os.open(path, os.O_PATH)
    isdir = stat.S_ISDIR(os.fstat(o_path_fd).st_mode)
    fd = pathref_reopen(o_path_fd, os.O_DIRECTORY if isdir else os.O_RDONLY, close_fd=True)

    try:
        rv = get_dosflags_impl(path, fd)
        return DOSFlag.flags_to_dict(rv)
    finally:
        os.close(fd)


def get_dosflags_impl(path: str, fd: int) -> int:
    fl = struct.unpack('L', fcntl.ioctl(fd, ZFS_IOC_GETDOSFLAGS, struct.pack('L', 0)))
    if not fl:
        raise CallError(f'Unable to retrieve attribute of {path!r} path')
    return fl[0]


def set_dosflags(path: str, dosflags: dict) -> None:
    o_path_fd = os.open(path, os.O_PATH)
    isdir = stat.S_ISDIR(os.fstat(o_path_fd).st_mode)
    fd = pathref_reopen(o_path_fd, os.O_DIRECTORY if isdir else os.O_RDWR, close_fd=True)

    try:
        current = get_dosflags_impl(path, fd)
        to_set = DOSFlag.flags_to_dict(current) | dosflags
        finalized = (current & ~DOSFlag.ALL) | DOSFlag.dict_to_flags(to_set)

        set_dosflags_impl(fd, path, finalized)
    finally:
        os.close(fd)


def set_dosflags_impl(fd: int, path: str, flags: int) -> None:
    fcntl.ioctl(fd, ZFS_IOC_SETDOSFLAGS, struct.pack('L', flags))
    if flags != get_dosflags_impl(path, fd):
        raise CallError(f'Unable to set dos flag at {path!r}')
