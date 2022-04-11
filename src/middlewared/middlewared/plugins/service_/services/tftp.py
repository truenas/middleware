from .base import SimpleService


class TFTPService(SimpleService):
    name = "tftp"

    etc = ["tftp"]

    systemd_unit = "tftpd-hpa"
