from .base import SimpleService


class TFTPService(SimpleService):
    name = "tftp"

    etc = ["tftp"]
    deprecated = True

    systemd_unit = "tftpd-hpa"
