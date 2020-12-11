from .base import SimpleService


class OpenVPNServerService(SimpleService):
    name = "openvpn_server"

    etc = ["ssl", "openvpn_server"]

    freebsd_rc = "openvpn_server"
    freebsd_pidfile = "/var/run/openvpn_server.pid"
    freebsd_procname = "openvpn"

    systemd_unit = "openvpn-server@server"
