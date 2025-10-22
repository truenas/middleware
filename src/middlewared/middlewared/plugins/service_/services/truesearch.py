from middlewared.plugins.service_.services.base import SimpleService


class TruesearchService(SimpleService):
    name = "truesearch"

    etc = ["truesearch"]
    reloadable = True

    systemd_unit = "truesearch"
