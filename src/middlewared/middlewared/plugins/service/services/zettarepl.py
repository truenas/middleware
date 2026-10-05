from .base import SimpleService


class ZettareplService(SimpleService):
    name = "zettarepl"

    systemd_unit = "zettarepl"
