from .base import SimpleService


class TruenasZfsrewritedService(SimpleService):
    name = "truenas_zfsrewrited"

    systemd_unit = "truenas_zfsrewrited"
