from middlewared.plugins.service_.services.base import SimpleService


class LibvirtdService(SimpleService):
    name = "libvirtd"

    systemd_unit = "libvirtd"

    etc = ["libvirt"]
