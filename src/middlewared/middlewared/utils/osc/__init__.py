import platform

SYSTEM = platform.system().upper()
IS_FREEBSD = SYSTEM == "FREEBSD"
IS_LINUX = SYSTEM == "LINUX"

from .linux import *  # noqa
