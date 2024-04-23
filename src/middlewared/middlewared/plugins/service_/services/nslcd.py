from .base import SimpleService


class NSSPamLdapdService(SimpleService):
    name = "nslcd"
    default_ha_propagate = False

    systemd_unit = "nslcd"
