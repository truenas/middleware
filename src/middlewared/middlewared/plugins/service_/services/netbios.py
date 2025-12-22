from .base import SimpleService


class NetBIOSService(SimpleService):
    name = "nmbd"
    may_run_on_standby = False

    systemd_unit = "nmbd"
