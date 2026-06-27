from .base import SimpleService


class NSCDService(SimpleService):
    name = "nscd"
    reloadable = True

    etc = ["nscd"]

    systemd_unit = "nscd"
