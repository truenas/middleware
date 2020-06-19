from .base import SimpleService


class RsyncService(SimpleService):
    name = "rsync"

    etc = ["rsync"]

    freebsd_rc = "rsyncd"
    freebsd_pidfile = "/var/run/rsyncd.pid"
    freebsd_procname = "rsync"

    systemd_unit = "rsync"
