from .base import SimpleService


class OpenVPNServerService(SimpleService):
    name = "openvpn_server"

    etc = ["ssl", "openvpn_server"]

    systemd_unit = "openvpn-server@server"
