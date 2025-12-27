import os
import pathlib

from middlewared.plugins.ups import UPS_POWERDOWN_FLAG_FILE


UPS_CONFPATH = '/etc/nut'
UPS_VARPATH = '/var/run/nut'
UPS_CONFIG = f'{UPS_CONFPATH}/ups.conf'
UPS_MONFILE = f'{UPS_CONFPATH}/upsmon.conf'
UPS_SCHEDFILE = f'{UPS_CONFPATH}/upssched.conf'
UPS_USERSFILE = f'{UPS_CONFPATH}/upsd.users'
UPS_DAEMONFILE = f'{UPS_CONFPATH}/upsd.conf'


def ups_config_perms(middleware):
    pathlib.Path(UPS_POWERDOWN_FLAG_FILE).unlink(missing_ok=True)


def render(service, middleware):
    ups_config_perms(middleware)
