from .base import SimpleService


class WSDService(SimpleService):
    name = "wsdd"

    etc = ["wsd"]

    systemd_unit = "wsdd"
