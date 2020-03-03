from .base import SimpleService


class OpenVPNServerService(SimpleService):
    name = "openvpn_server"

    etc = ["ssl", "openvpn_server"]

    freebsd_rc = "openvpn"
    freebsd_pidfile = "/var/run/openvpn_server.pid"
