import os
import shutil

UPS_CONFPATH = '/usr/local/etc/nut'
UPS_VARPATH = '/var/db/nut'


def generate_ups_config(middleware):
    if os.path.isdir(UPS_CONFPATH):
        shutil.rmtree(UPS_CONFPATH)

    os.makedirs(UPS_CONFPATH)
    os.makedirs(UPS_VARPATH, exist_ok=True)

    nut_group = middleware.call_sync('group.query', [['group', '=', 'nut']], {'get': True})
    os.chown(UPS_VARPATH, 0, nut_group['gid'])
    os.chmod(UPS_VARPATH, 0o770)


def render(service, middleware):
    generate_ups_config(middleware)
