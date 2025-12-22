from .base import SimpleService


class FTPService(SimpleService):
    name = "ftp"
    reloadable = True
    may_run_on_standby = False

    etc = ["ftp"]

    systemd_unit = "proftpd"
