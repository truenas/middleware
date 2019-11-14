import platform

if platform.system().lower() == "freebsd":
    from .freebsd import *


if platform.system().lower() == "linux":
    from .linux import *
