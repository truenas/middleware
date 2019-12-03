import platform

platform_name = None

if platform.system().lower() == "freebsd":
    from .freebsd import *  # noqa
    platform_name = 'FREEBSD'


if platform.system().lower() == "linux":
    from .linux import *  # noqa
    platform_name = 'LINUX'
