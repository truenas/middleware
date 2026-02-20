import os
import shutil


UPS_CONFPATH = '/etc/nut'
UPS_USER = 'nut'
UPS_VARPATH = '/var/run/nut'
UPSSCHED_VARPATH = '/var/run/nut/private'


def generate_ups_config(middleware):
    if os.path.isdir(UPS_CONFPATH):
        shutil.rmtree(UPS_CONFPATH)

    os.makedirs(UPS_CONFPATH)
    os.makedirs(UPS_VARPATH, exist_ok=True)
    os.makedirs(UPSSCHED_VARPATH, exist_ok=True)

    ups_group = middleware.call_sync('group.query', [['group', '=', UPS_USER]], {'get': True})
    os.chown(UPS_VARPATH, 0, ups_group['gid'])
    os.chmod(UPS_VARPATH, 0o775)
    os.chmod(UPSSCHED_VARPATH, 0o770)


def render(service, middleware, render_ctx):
    generate_ups_config(middleware)
