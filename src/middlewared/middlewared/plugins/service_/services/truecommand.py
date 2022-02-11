from .base import SimpleService


class TruecommandService(SimpleService):
    name = 'truecommand'

    etc = ['rc', 'truecommand']

    freebsd_rc = 'wireguard'
    freebsd_procname = 'wg-quick'
    freebsd_proc_arguments_match = True

    systemd_unit = 'wg-quick@wg0'
