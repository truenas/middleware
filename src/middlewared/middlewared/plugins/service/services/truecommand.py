from middlewared.plugins.truecommand.utils import WIREGUARD_INTERFACE_NAME

from .base import SimpleService


class TruecommandService(SimpleService):
    name = 'truecommand'

    etc = ['rc', 'truecommand']
    may_run_on_standby = False

    systemd_unit = f'wg-quick@{WIREGUARD_INTERFACE_NAME}'
