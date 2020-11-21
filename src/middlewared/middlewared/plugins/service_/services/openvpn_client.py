from .base import SimpleService


class OpenVPNClientService(SimpleService):
    name = "openvpn_client"

    etc = ["openvpn_client"]

    freebsd_rc = "openvpn_client"
    freebsd_pidfile = "/var/run/openvpn_client.pid"
    freebsd_procname = "openvpn"

    systemd_unit = "openvpn-client@client"
