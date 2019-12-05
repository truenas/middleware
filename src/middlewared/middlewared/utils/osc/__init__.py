import platform

if platform.system().lower() == "freebsd":
    from .freebsd import *  # noqa


if platform.system().lower() == "linux":
    from .linux import *  # noqa
