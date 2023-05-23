from .base import SimpleService


class OpenVPNClientService(SimpleService):
    name = "openvpn_client"
    deprecated = True
    etc = ["openvpn_client"]
    systemd_unit = "openvpn-client@client"
