from .base import SimpleService


class NFSService(SimpleService):
    name = "nfs"
    reloadable = True

    etc = ["nfsd"]

    systemd_unit = "nfs-server"
