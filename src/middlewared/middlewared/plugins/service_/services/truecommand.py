from .base import SimpleService


class TruecommandService(SimpleService):
    name = 'truecommand'

    etc = ['rc', 'truecommand']

    systemd_unit = 'wg-quick@wg0'
