from .base import SimpleService


class OpenVPNServerService(SimpleService):
    name = "openvpn_server"
    deprecated = True
    etc = ["ssl", "openvpn_server"]
    systemd_unit = "openvpn-server@server"
