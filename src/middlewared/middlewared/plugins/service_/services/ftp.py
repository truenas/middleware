from .base import SimpleService


class FTPService(SimpleService):
    name = "ftp"
    reloadable = True

    etc = ["ftp"]

    freebsd_rc = "proftpd"
    freebsd_pidfile = "/var/run/proftpd.pid"

    systemd_unit = "proftpd"
