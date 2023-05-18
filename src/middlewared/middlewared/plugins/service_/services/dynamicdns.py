from .base import SimpleService


class DynamicDNSService(SimpleService):
    name = "dynamicdns"

    etc = ["inadyn"]
    deprecated = True

    systemd_unit = "inadyn"
