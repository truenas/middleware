from .base import SimpleService


class TruenasSmbhadService(SimpleService):
    name = "truenas_smbhad"
    reloadable = True
    restartable = True

    etc = ["truenas_smbhad"]

    systemd_unit = "truenas-smbhad"
