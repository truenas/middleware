from .base import SimpleService


class DynamicDNSService(SimpleService):
    name = "dynamicdns"

    etc = ["inadyn"]

    freebsd_rc = "inadyn"

    systemd_unit = "inadyn"
