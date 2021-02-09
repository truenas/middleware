from middlewared.utils.osc import IS_FREEBSD

from .base import SimpleService


class TFTPService(SimpleService):
    name = "tftp"

    etc = ["inetd"] if IS_FREEBSD else ["tftp"]

    freebsd_rc = "inetd"
    freebsd_pidfile = "/var/run/inetd.pid"

    systemd_unit = "tftpd-hpa"
