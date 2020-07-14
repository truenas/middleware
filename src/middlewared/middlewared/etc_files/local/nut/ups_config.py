import os
import shutil

from middlewared.utils import osc

if osc.IS_LINUX:
    UPS_CONFPATH = '/etc/nut'
    UPS_USER = 'nut'
    UPS_VARPATH = '/var/run/nut'
else:
    UPS_CONFPATH = '/usr/local/etc/nut'
    UPS_USER = 'uucp'
    UPS_VARPATH = '/var/db/nut'


def generate_ups_config(middleware):
    if os.path.isdir(UPS_CONFPATH):
        shutil.rmtree(UPS_CONFPATH)

    os.makedirs(UPS_CONFPATH)
    os.makedirs(UPS_VARPATH, exist_ok=True)

    ups_group = middleware.call_sync('group.query', [['group', '=', UPS_USER]], {'get': True})
    os.chown(UPS_VARPATH, 0, ups_group['gid'])
    os.chmod(UPS_VARPATH, 0o770)


def render(service, middleware):
    generate_ups_config(middleware)
