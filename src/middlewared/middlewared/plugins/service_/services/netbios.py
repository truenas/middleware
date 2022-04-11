from .base import SimpleService


class NetBIOSService(SimpleService):
    name = "nmbd"

    systemd_unit = "nmbd"
