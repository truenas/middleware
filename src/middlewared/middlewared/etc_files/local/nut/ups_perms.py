import os

UPS_CONFPATH = '/usr/local/etc/nut'
UPS_VARPATH = '/var/db/nut'
UPS_CONFIG = f'{UPS_CONFPATH}/ups.conf'
UPS_MONFILE = f'{UPS_CONFPATH}/upsmon.conf'
UPS_SCHEDFILE = f'{UPS_CONFPATH}/upssched.conf'
UPS_USERSFILE = f'{UPS_CONFPATH}/upsd.users'
UPS_DAEMONFILE = f'{UPS_CONFPATH}/upsd.conf'


def ups_config_perms(middleware):
    ups_config = middleware.call_sync('ups.config')
    uucp_group = middleware.call_sync('group.query', [['group', '=', 'uucp']], {'get': True})
    master_mode_files = (UPS_CONFIG, UPS_USERSFILE, UPS_DAEMONFILE)

    for file in master_mode_files:
        if ups_config['mode'].lower() != 'master':
            os.remove(file)
        else:
            os.chown(file, 0, uucp_group['gid'])
            os.chmod(file, 0o440)

    for file in (UPS_MONFILE, UPS_SCHEDFILE):
        os.chown(file, 0, uucp_group['gid'])
        os.chmod(file, 0o440)


async def render(service, middleware):
    await middleware.run_in_thread(ups_config_perms, middleware)
