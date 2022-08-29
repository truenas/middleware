from middlewared.plugins.service_.services.base import SimpleService


class OpenIpmiService(SimpleService):
    name = "openipmi"
    systemd_unit = "openipmi"
