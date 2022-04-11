from .base import SimpleService


class DynamicDNSService(SimpleService):
    name = "dynamicdns"

    etc = ["inadyn"]

    systemd_unit = "inadyn"
