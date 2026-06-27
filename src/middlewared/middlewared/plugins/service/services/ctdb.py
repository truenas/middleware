from .base import SimpleService


class CTDBService(SimpleService):
    name = "ctdb"
    etc = ["ctdb"]

    systemd_unit = "ctdb"
