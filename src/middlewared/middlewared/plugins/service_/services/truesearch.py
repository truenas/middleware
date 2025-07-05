from .base import SimpleService


class TrueSearchService(SimpleService):
    name = "truesearch"
    reloadable = True

    systemd_unit = "truesearch"