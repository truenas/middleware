from .base import SimpleService


class FTPService(SimpleService):
    name = "ftp"

    etc = ["ftp"]

    freebsd_rc = "proftpd"
    freebsd_pidfile = "/var/run/proftpd.pid"
