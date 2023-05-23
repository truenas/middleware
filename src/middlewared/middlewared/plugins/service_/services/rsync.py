from .base import SimpleService


class RsyncService(SimpleService):
    name = "rsync"
    deprecated = True
    etc = ["rsync"]
    systemd_unit = "rsync"
