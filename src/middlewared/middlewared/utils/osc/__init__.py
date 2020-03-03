import platform

SYSTEM = platform.system().upper()
IS_FREEBSD = SYSTEM == "FREEBSD"
IS_LINUX = SYSTEM == "LINUX"

if IS_FREEBSD:
    from .freebsd import *  # noqa

if IS_LINUX:
    from .linux import *  # noqa
