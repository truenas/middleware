from .base import SimpleService


class FTPService(SimpleService):
    name = "ftp"
    reloadable = True

    etc = ["ftp"]

    systemd_unit = "proftpd"
