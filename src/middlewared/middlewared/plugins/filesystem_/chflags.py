import fcntl
import os
import struct

from middlewared.service import CallError


F_IOC_GETFLAGS = 0x80086601
F_IOC_SETFLAGS = 0x40086602
IMMUTABLE_FL = 16


def get_flags(path: str) -> int:
    fd = os.open(path, os.O_RDONLY)
    try:
        return get_flags_impl(path, fd)
    finally:
        os.close(fd)


def get_flags_impl(path: str, fd: int) -> int:
    fl = struct.unpack('i', fcntl.ioctl(fd, F_IOC_GETFLAGS, struct.pack('i', 0)))
    if not fl:
        raise CallError(f'Unable to retrieve attribute of {path!r} path')
    return fl[0]


def set_immutable(path: str, set_flag: bool) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        set_immutable_impl(fd, path, set_flag)
    finally:
        os.close(fd)


def set_immutable_impl(fd: int, path: str, set_flag: bool) -> None:
    existing_flags = get_flags_impl(path, fd)
    new_flags = existing_flags | IMMUTABLE_FL if set_flag else existing_flags & ~IMMUTABLE_FL
    fcntl.ioctl(fd, F_IOC_SETFLAGS, struct.pack('i', new_flags))
    if new_flags != get_flags_impl(path, fd):
        raise CallError(f'Unable to {"set" if set_flag else "unset"} immutable flag at {path!r}')
