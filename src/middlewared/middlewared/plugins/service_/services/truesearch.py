from middlewared.plugins.service_.services.base import SimpleService


class TruesearchService(SimpleService):
    name = "truesearch"

    etc = ["truesearch"]
    reloadable = True
    may_run_on_standby = False

    systemd_unit = "truesearch"
    systemd_unit_timeout = 6  # It normally truesearch takes 5+ seconds to stop
