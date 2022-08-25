from middlewared.plugins.service_.services.base import SimpleService


class LibvirtdService(SimpleService):
    name = "openipmi"
    systemd_unit = "openipmi"
