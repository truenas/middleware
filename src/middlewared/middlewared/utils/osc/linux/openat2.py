import os
import ctypes
from enum import IntFlag

__all__ = ["openat2", "ResolveFlags"]

AT_FDCWD = -100

# See linux/openat2.h
__NR_openat2 = 437


class ResolveFlags(IntFlag):
    # fcntl.h
    RESOLVE_NO_XDEV = 0x01
    RESOLVE_NO_MAGICLINKS = 0x02
    RESOLVE_NO_SYMLINKS = 0x04
    RESOLVE_BENEATH = 0x08
    RESOLVE_IN_ROOT = 0x10
    RESOLVE_CACHED = 0x20
    VALID_FLAGS = 0x3f


class OpenHow(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_uint64),
        ("mode", ctypes.c_uint64),
        ("resolve", ctypes.c_uint64)
    ]


def openat2(path, flags, mode=0, resolve=0, dirfd=AT_FDCWD):
    path = path.encode() if isinstance(path, str) else path

    if invalid_resolve := resolve & ~ResolveFlags.VALID_FLAGS:
        raise ValueError(f'{hex(invalid_resolve)}: unsupported resolve flags')

    _libc = ctypes.CDLL('libc.so.6', use_errno=True)
    _func = _libc.syscall
    _func.restype = ctypes.c_int
    _func.argstypes = (
        ctypes.c_uint64,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.POINTER(OpenHow),
        ctypes.c_uint64
    )
    how = OpenHow(flags, mode, resolve)
    result = _func(__NR_openat2, dirfd, path, ctypes.byref(how), ctypes.sizeof(OpenHow))
    if result < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    else:
        return result
