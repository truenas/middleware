import contextlib
import itertools
import os
import re
import subprocess
import sysctl

from middlewared.utils.io import write_if_changed

NFS_BINDIP_NOTFOUND = '/tmp/.nfsbindip_notfound'
RE_FIRMWARE_VERSION = re.compile(r'Firmware Revision\s*:\s*(\S+)', re.M)


def get_context(middleware):
    context = {
        'is_freenas': middleware.call_sync('system.is_freenas'),
        'failover_licensed': False,
        'failover_status': 'SINGLE',
    }

    if not context['is_freenas']:
        context['failover_licensed'] = middleware.call_sync('failover.licensed')
        context['failover_status'] = middleware.call_sync('failover.status')

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


def collectd_config(middleware, context):
    if context['is_freenas'] or context['failover_status'] != 'BACKUP':
        yield 'collectd_enable="YES"'
        yield 'rrdcached_enable="YES"'

        rrdcached_flags = '-s www -l /var/run/rrdcached.sock -p /var/run/rrdcached.pid'
        sysds = middleware.call_sync('systemdataset.config')
        if sysds['pool'] in ('', 'freenas-boot'):
            rrdcached_flags += ' -w 3600 -f 7200'
        yield f'rrdcached_flags="{rrdcached_flags}"'
    else:
        return []


def geli_config(middleware, context):
    if context['failover_licensed']:
        return []
    providers = []
    for ed in middleware.call_sync(
        'datastore.query',
        'storage.encrypteddisk',
        [('encrypted_volume__vol_encrypt', '=', 1)],
    ):
        providers.append(ed['encrypted_provider'])
        provider = ed['encrypted_provider'].replace('/', '_').replace('-', '_')
        key = f'/data/geli/{ed["encrypted_volume"]["vol_encryptkey"]}.key'
        yield f'geli_{provider}_flags="-p -k {key}"'
    yield f'geli_devices="{" ".join(providers)}"'


def host_config(middleware, context):
    config = middleware.call_sync('network.configuration.config')
    yield f'hostname="{config["hostname_local"]}.{config["domain"]}"'

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


def kbdmap_config(middleware, context):
    general = middleware.call_sync('system.general.config')
    if general['kbdmap']:
        yield f'keymap="{general["kbdmap"]}"'
    else:
        return []


def ldap_config(middleware, context):
    ldap = middleware.call_sync('datastore.config', 'directoryservice.ldap', {'prefix': 'ldap_'})
    yield f'nslcd_enable="{"YES" if ldap["enable"] else "NO"}"'


def lldp_config(middleware, context):
    lldp = middleware.call_sync('lldp.config')
    ladvd_flags = ['-a']
    if lldp['intdesc']:
        ladvd_flags.append('-z')
    if lldp['country']:
        ladvd_flags += ['-c', lldp['country']]
    if lldp['location']:
        ladvd_flags += ['-l', rf'\"{lldp["location"]}\"']
    yield f'ladvd_flags="{" ".join(ladvd_flags)}"'


def services_config(middleware, context):
    services = middleware.call_sync('datastore.query', 'services.services', [], {'prefix': 'srv_'})
    mapping = {
        'afp': ['netatalk'],
        'cifs': ['samba_server', 'smbd', 'nmbd', 'winbindd'],
        'dynamicdns': ['inadyn'],
        'ftp': ['proftpd'],
        'iscsitarget': ['ctld'],
        'lldp': ['ladvd'],
        's3': ['minio'],
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
            'netdata': ['netdata'],
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


def nfs_config(middleware, context):
    nfs = middleware.call_sync('nfs.config')

    mountd_flags = ['-rS']
    if nfs['mountd_log']:
        mountd_flags.append('-l')
    if nfs['allow_nonroot']:
        mountd_flags.append('-n')
    if nfs['mountd_port']:
        mountd_flags += ['-p', str(nfs['mountd_port'])]

    statd_flags = []
    lockd_flags = []
    if nfs['statd_lockd_log']:
        statd_flags.append('-d')
        lockd_flags += ['-d', '10']
    if nfs['rpcstatd_port']:
        statd_flags += ['-p', str(nfs['rpcstatd_port'])]
    if nfs['rpclockd_port']:
        lockd_flags += ['-p', str(nfs['rpclockd_port'])]

    nfs_server_flags = ['-t', '-n', str(nfs['servers'])]
    if nfs['udp']:
        nfs_server_flags.append('-u')

    # Make sure IPs bind to NFS are in the interfaces (exist!) #16044
    if nfs['bindip']:
        found = False
        for iface in middleware.call_sync('interface.query'):
            for alias in iface['state']['aliases']:
                if alias['address'] in nfs['bindip']:
                    found = True
                    break
            if found:
                break

        if found:
            found = True
            # FIXME: stop using sentinel file
            with contextlib.suppress(Exception):
                os.unlink(NFS_BINDIP_NOTFOUND)

            ips = list(itertools.chain(*[['-h', i] for i in nfs['bindip']]))
            mountd_flags += ips
            nfs_server_flags += ips
            statd_flags += ips
            yield f'rpcbind_flags="{" ".join(ips)}"'
        else:
            with open(NFS_BINDIP_NOTFOUND, 'w'):
                pass

    yield f'nfs_server_flags="{" ".join(nfs_server_flags)}"'
    yield f'rpc_statd_flags="{" ".join(statd_flags)}"'
    yield f'rpc_lockd_flags="{" ".join(lockd_flags)}"'
    yield f'mountd_flags="{" ".join(mountd_flags)}"'

    enabled = middleware.call_sync(
        'datastore.query', 'services.services', [
            ('srv_service', '=', 'nfs'), ('srv_enable', '=', True),
        ]
    )
    if not enabled:
        return []

    if nfs['v4']:
        yield 'nfsv4_server_enable="YES"'

        gssd = 'NO'
        if nfs['v4_krb'] and middleware.call_sync('datastore.query', 'directoryservice.kerberoskeytab'):
            gssd = 'YES'

            gc = middleware.call_sync("datastore.config", "network.globalconfiguration")
            if gc["gc_hostname_virtual"] and gc["gc_domain"]:
                yield f'nfs_server_vhost="{gc["gc_hostname_virtual"]}.{gc["gc_domain"]}"'

        yield f'gssd_enable="{gssd}"'

        if nfs['v4_v3owner']:
            yield 'nfsuserd_enable="NO"'
            # Per RFC7530, sending NFSv3 style UID/GIDs across the wire is now allowed
            # You must have both of these sysctl's set to allow the desired functionality
            sysctl.filter('vfs.nfsd.enable_stringtouid')[0].value = 1
            sysctl.filter('vfs.nfs.enable_uidtostring')[0].value = 1
        else:
            yield 'nfsuserd_enable="YES"'
            sysctl.filter('vfs.nfsd.enable_stringtouid')[0].value = 0
            sysctl.filter('vfs.nfs.enable_uidtostring')[0].value = 0
    else:
        yield 'nfsv4_server_enable="NO"'
        if nfs['userd_manage_gids']:
            yield 'nfsuserd_enable="YES"'
            yield 'nfsuserd_flags="-manage-gids"'


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


def nut_config(middleware, context):
    enabled = middleware.call_sync(
        'datastore.query', 'services.services', [
            ('srv_service', '=', 'ups'), ('srv_enable', '=', True),
        ]
    )
    # FIXME: UPS will only work if "Start on boot" is enabled
    if not enabled:
        return []

    ups = middleware.call_sync('ups.config')
    if ups['mode'] == 'MASTER':
        yield 'nut_enable="YES"'
        yield 'nut_upsshut="NO"'
        yield f'nut_upslog_ups="{ups["identifier"]}"'
    else:
        yield f'nut_upslog_ups="{ups["identifier"]}@{ups["remotehost"]}:{ups["remoteport"]}"'
    yield 'nut_upslog_enable="YES"'
    yield 'nut_upsmon_enable="YES"'


def powerd_config(middleware, context):
    value = 'YES' if middleware.call_sync('system.advanced.config')['powerdaemon'] else 'NO'
    yield f'powerd_enable="{value}"'


def s3_config(middleware, context):
    s3 = middleware.call_sync('s3.config')
    yield f'minio_disks="{s3["storage_path"]}"'
    yield f'minio_address="{s3["bindip"]}:{s3["bindport"]}"'
    browser = 'MINIO_BROWSER=off \\\n' if not s3['browser'] else ''
    yield (
        'minio_env="\\\n'
        f'MINIO_ACCESS_KEY={s3["access_key"]} \\\n'
        f'MINIO_SECRET_KEY={s3["secret_key"]} \\\n'
        f'{browser}'
        '"'
    )


def smart_config(middleware, context):
    smart = middleware.call_sync('smart.config')
    yield f'smart_daemon_flags="-i {smart["interval"] * 60}"'


def snmp_config(middleware, context):
    yield 'snmpd_conffile="/etc/local/snmpd.conf"'
    loglevel = middleware.call_sync('snmp.config')['loglevel']
    yield f'snmpd_flags="-LS{loglevel}d"'


def staticroute_config(middleware, context):
    ipv4_routes = []
    ipv6_routes = []
    for sr in middleware.call_sync('staticroute.query'):
        route = f'freenas{sr["id"]}'
        if ':' in sr['destination']:
            ipv6_routes.append(route)
            rcprefix = 'ipv6_'
        else:
            ipv4_routes.append(route)
            rcprefix = ''
        yield f'{rcprefix}route_{route}="-net {sr["destination"]} {sr["gateway"]}"'
    if ipv4_routes:
        yield f'static_routes="{" ".join(ipv4_routes)}"'
    if ipv6_routes:
        yield f'ipv6_static_routes="{" ".join(ipv6_routes)}"'


def tftp_config(middleware, context):
    tftp = middleware.call_sync('tftp.config')
    yield f'inetd_flags="-wW -C 60 -a {tftp["host"]}"'


def truenas_config(middleware, context):
    if context['is_freenas'] or not context['failover_licensed']:
        yield 'failover_enable="NO"'
    else:
        yield 'failover_enable="YES"'


def tunable_config(middleware, context):
    for tun in middleware.call_sync('tunable.query', [
        ('type', '=', 'RC'), ('enabled', '=', True)
    ]):
        yield f'{tun["var"]}="{tun["value"]}"'
    return []


def vmware_config(middleware, context):
    try:
        subprocess.run(
            ['vmware-checkvm'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        yield 'vmware_guestd_enable="NO"'
    except Exception:
        middleware.logger.warn('Failed to run vmware-checkvm', exc_info=True)
        return []
    else:
        yield 'vmware_guestd_enable="YES"'


def _bmc_watchdog_is_broken():
    cp = subprocess.run(['ipmitool', 'mc', 'info'], capture_output=True, errors='ignore')
    reg = RE_FIRMWARE_VERSION.search(cp.stdout)
    if not reg:
        return False

    version = reg.group(1).split('.')
    if len(version) > 2:
        return False

    try:
        return [int(i) for i in version[:2]] < [0, 30]
    except ValueError:
        return False


def watchdog_config(middleware, context):
    if context['is_freenas']:
        # Bug #7337 -- blacklist AMD systems for now
        model = sysctl.filter('hw.model')
        if not model or 'AMD' not in model[0].value:
            product = subprocess.run(
                ['dmidecode', '-s', 'baseboard-product-name'],
                capture_output=True,
                errors='ignore',
            ).stdout.split('\n')[0].strip()

            if product in ('C2750D4I', 'C2550D4I') and _bmc_watchdog_is_broken():
                return [
                    'watchdogd_enable="YES"',
                    'watchdogd_flags="-t 30 --softtimeout --softtimeout-action log,printf '
                    '--pretimeout 15 --pretimeout-action log,printf -e \'sleep 1\' -w -T 3"',
                ]
            elif product not in ('X9DR3-F', 'X9DR3-LN4F+'):
                return [
                    'watchdogd_enable="YES"',
                    'watchdogd_flags="--pretimeout 5 --pretimeout-action log,printf"',
                ]
    return ['watchdogd_enable="NO"']


def zfs_config(middleware, context):
    if middleware.call_sync('datastore.query', 'storage.volume'):
        yield 'zfs_enable="YES"'


def render(service, middleware):

    context = get_context(middleware)

    rcs = []
    for i in (
        services_config,
        asigra_config,
        collectd_config,
        geli_config,
        host_config,
        kbdmap_config,
        ldap_config,
        lldp_config,
        nfs_config,
        nis_config,
        nut_config,
        powerd_config,
        s3_config,
        smart_config,
        snmp_config,
        staticroute_config,
        tftp_config,
        truenas_config,
        tunable_config,
        vmware_config,
        watchdog_config,
        zfs_config,
    ):
        try:
            rcs += list(i(middleware, context))
        except Exception:
            middleware.logger.error('Failed to generate %s', i.__name__, exc_info=True)

    write_if_changed('/etc/rc.conf.freenas', '\n'.join(rcs) + '\n')
