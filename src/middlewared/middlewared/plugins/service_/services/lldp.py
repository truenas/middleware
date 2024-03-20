from .base import SimpleService


class LLDPService(SimpleService):
    name = "lldp"

    etc = []

    freebsd_rc = "ladvd"
    freebsd_pidfile = "/var/run/ladvd.pid"

    systemd_unit = "ladvd"
