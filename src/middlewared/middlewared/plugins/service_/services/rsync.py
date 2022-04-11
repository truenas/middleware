from .base import SimpleService


class RsyncService(SimpleService):
    name = "rsync"

    etc = ["rsync"]

    systemd_unit = "rsync"
