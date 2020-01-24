import platform

SYSTEM = platform.system().upper()

if SYSTEM == "FREEBSD":
    from .freebsd import *  # noqa


if SYSTEM == "LINUX":
    from .linux import *  # noqa
