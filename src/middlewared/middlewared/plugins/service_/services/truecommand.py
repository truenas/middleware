from .base import SimpleService


class TruecommandService(SimpleService):
    name = 'truecommand'

    etc = ['rc', 'truecommand']

    freebsd_rc = 'wireguard'
    freebsd_procname = 'wireguard-go'

    systemd_unit = 'wg-quick@wg0'
