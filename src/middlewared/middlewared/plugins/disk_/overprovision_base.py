import errno

from middlewared.service_exception import CallError


class CanNotBeOverprovisionedException(CallError):
    def __init__(self, devname):
        super().__init__(f"{devname} cannot be overprovisioned", errno.EINVAL)
