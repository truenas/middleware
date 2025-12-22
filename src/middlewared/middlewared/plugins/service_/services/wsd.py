from .base import SimpleService


class WSDService(SimpleService):
    name = "wsdd"
    may_run_on_standby = False

    etc = ["wsd"]

    systemd_unit = "wsdd"
