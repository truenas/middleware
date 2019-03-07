import os


def get_context(middleware):
    context = {
        'is_freenas': middleware.call_sync('system.is_freenas'),
        'failover_licensed': False,
    }

    if not context['is_freenas']:
        context['failover_licensed'] = middleware.call_sync('failover.licensed')

    return context


def asigra_config(middleware, context):
    if context['is_freenas']:
        return []

    yield (
        'dssystem_env="PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin:'
        '/root/bin"'
    )
    yield 'postgresql_user="pgsql"'

    pgsql_path = middleware.call_sync('asigra.config')['filesystem']
    if not os.path.exists(pgsql_path):
        pgsql_path = '/usr/local/pgsql/data'
    yield f'postgresql_data="{pgsql_path}"'


def host_config(middleware, context):
    config = middleware.call_sync('network.configuration.config')
    yield f'hostname="{config["hostname"]}.{config["domain"]}"'

    if config['ipv4gateway']:
        yield f'defaultrouter="{config["ipv4gateway"]}"'

    if config['ipv6gateway']:
        yield f'ipv6_defaultrouter="{config["ipv6gateway"]}"'

    if config['netwait_enabled']:
        yield 'netwait_enable="YES"'
        if not config['netwait_ip']:
            if config['ipv4gateway']:
                config['netwait_ip'] = config['ipv4gateway']
            elif config['ipv6gateway']:
                config['netwait_ip'] = config['ipv6gateway']
        yield f'netwait_ip="{config["netwait_ip"]}"'


def services_config(middleware, context):
    services = middleware.call_sync('datastore.query', 'services.services', [], {'prefix': 'srv_'})
    mapping = {
        'afp': ['netatalk'],
        'cifs': ['samba_server', 'smbd', 'nmbd', 'winbindd'],
        'dynamicdns': ['inadyn'],
        'ftp': ['proftpd'],
        'iscsitarget': ['ctld'],
        'lldp': ['ladvd'],
        'netdata': ['netdata'],
        'nfs': ['nfs_server', 'rpc_lockd', 'rpc_statd', 'mountd', 'nfsd', 'rpcbind'],
        'rsync': ['rsyncd'],
        'snmp': ['snmpd', 'snmp_agent'],
        'ssh': ['openssh'],
        'tftp': ['inetd'],
        'webdav': ['apache24'],
    }

    if context['failover_licensed'] is False:
        # These services are handled by HA script
        # smartd #76242
        mapping.update({
            'smartd': ['smartd_daemon'],
            'asigra': ['dssystem', 'postgresql'],
        })

    for service in services:
        rcs_enable = mapping.get(service['service'])
        if not rcs_enable:
            continue
        value = 'YES' if service['enable'] else 'NO'
        for rc_enable in rcs_enable:
            yield f'{rc_enable}_enable="{value}"'


def nis_config(middleware, context):
    nis = middleware.call_sync('datastore.config', 'directoryservice.nis', {'prefix': 'nis_'})
    if not nis['enable'] or not nis['domain']:
        return []

    domain = nis['domain']
    if nis['servers']:
        domain += ',' + nis['servers']

    yield f'nisdomainname="{nis["domain"]}"'
    yield 'nis_client_enable="YES"'

    flags = ['-S', domain]
    if nis['secure_mode']:
        flags.append('-s')
    if nis['manycast']:
        flags.append('-m')
    yield f'nis_client_flags="{" ".join(flags)}"'


def powerd_config(middleware, context):
    value = 'YES' if middleware.call_sync('system.advanced.config')['powerdaemon'] else 'NO'
    yield f'powerd_enable="{value}"'


def snmp_config(middleware, context):
    yield 'snmpd_conffile="/etc/local/snmpd.conf"'
    loglevel = middleware.call_sync('snmp.config')['loglevel']
    yield f'snmpd_flags="-LS{loglevel}d"'


def render(service, middleware):

    context = get_context(middleware)

    rcs = []
    for i in (
        services_config,
        asigra_config,
        host_config,
        nis_config,
        powerd_config,
        snmp_config,
    ):
        rcs += list(i(middleware, context))

    with open('/etc/rc.conf.freenas', 'w') as f:
        f.write('\n'.join(rcs) + '\n')
