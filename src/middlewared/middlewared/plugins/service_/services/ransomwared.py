from .base import SimpleService


class RansomwaredService(SimpleService):
    name = "ransomwared"

    systemd_unit = "ransomwared"
