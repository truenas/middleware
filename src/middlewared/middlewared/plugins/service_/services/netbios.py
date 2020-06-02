from .base import SimpleService


class NetBIOSService(SimpleService):
    name = "nmbd"

    freebsd_rc = "nmbd"

    systemd_unit = "nmbd"
