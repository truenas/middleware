from middlewared.plugins.service.services.base import SimpleService


class OpenIpmiService(SimpleService):
    name = "openipmi"
    systemd_unit = "openipmi"
