from .base import SimpleService


class TruenasZfstierdService(SimpleService):
    name = "truenas_zfstierd"

    systemd_unit = "truenas_zfstierd"
