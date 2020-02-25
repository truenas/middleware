from .base import SimpleService


class TFTPService(SimpleService):
    name = "tftp"

    etc = ["inetd"]

    freebsd_rc = "inetd"
    freebsd_pidfile = "/var/run/inetd.pid"
