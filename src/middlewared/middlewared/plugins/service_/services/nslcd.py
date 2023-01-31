from .base import SimpleService


class NSSPamLdapdService(SimpleService):
    name = "nslcd"

    systemd_unit = "nslcd"
