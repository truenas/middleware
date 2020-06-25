from .base import SimpleService


class WSDService(SimpleService):
    name = "wsdd"

    freebsd_rc = "wsdd"

    systemd_unit = "wsdd"
