__author__ = 'jceel'

import ctypes

def read_sysctl(name):
    libc = ctypes.CDLL("libc.so.7")
    size = ctypes.c_uint(0)
    libc.sysctlbyname(name, None, ctypes.byref(size), None, 0)
    buf = ctypes.c_char_p(" " * size.value)
    libc.sysctlbyname(name, buf, ctypes.byref(size), None, 0)

    return buf.value