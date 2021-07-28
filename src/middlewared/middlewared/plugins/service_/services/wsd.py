from .base import SimpleService


class WSDService(SimpleService):
    name = "wsdd"

    etc = ["wsd"]

    freebsd_rc = "wsdd"

    systemd_unit = "wsdd"
