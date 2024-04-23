from .base import SimpleService


class WSDService(SimpleService):
    name = "wsdd"
    default_ha_propagate = False

    etc = ["wsd"]

    systemd_unit = "wsdd"
