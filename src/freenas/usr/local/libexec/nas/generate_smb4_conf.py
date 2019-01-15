#!/usr/local/bin/python

from middlewared.client import Client
from middlewared.client.utils import Struct

import os
import pwd
import re
import sys
import socket
import subprocess
import tempfile
import time
import logging
import logging.config

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[%(name)s:%(lineno)s] %(message)s'
        },
    },
    'handlers': {
        'syslog': {
            'level': 'DEBUG',
            'class': 'logging.handlers.SysLogHandler',
            'formatter': 'simple',
        }
    },
    'loggers': {
        '': {
            'handlers': ['syslog'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
})

truenas_params = {
    'is_truenas_ha': False,
    'failover_status': 'DEFAULT',
    'smb_ha_mode': 'LEGACY',
}

from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.log import log_traceback
from freenasUI.common.freenassysctl import freenas_sysctl as fs

log = logging.getLogger('generate_smb4_conf')


def qw(w):
    return '"%s"' % w.replace('"', '\\"')


def debug_SID(str):
    if str:
        print("XXX: %s" % str, file=sys.stderr)
    p = pipeopen("/usr/local/bin/net -d 0 getlocalsid")
    out, _ = p.communicate()
    if out:
        print("XXX: %s" % out, file=sys.stderr)


def smb4_get_system_SID():
    SID = None

    p = pipeopen("/usr/local/bin/net -d 0 getlocalsid")
    net_out = p.communicate()
    if p.returncode != 0:
        return None
    if not net_out:
        return None

    net_out = net_out[0]

    parts = net_out.split()
    try:
        SID = parts[5]
    except Exception as e:
        log.debug(
            'The following exception occured while trying to obtain system SID: {0}'.format(e)
        )
        log_traceback(log=log)
        SID = None

    return SID


def smb4_get_domain_SID():
    SID = None

    p = pipeopen("/usr/local/bin/net -d 0 getdomainsid")
    net_out = p.communicate()
    if p.returncode != 0:
        return None
    if not net_out:
        return None

    net_out = net_out[0]

    parts = net_out.split()
    try:
        SID = parts[5]
    except Exception as e:
        log.debug(
            'The following exception occured while trying to obtain system SID: {0}'.format(e)
        )
        log_traceback(log=log)
        SID = None

    return SID


def smb4_get_database_SID(client):
    SID = None

    try:
        cifs = Struct(client.call('datastore.query', 'services.cifs', None, {'get': True}))
        if cifs:
            SID = cifs.cifs_SID
    except Exception as e:
        log.debug(
            'The following exception occured while trying to obtain database SID: {0}'.format(e)
        )
        log_traceback(log=log)
        SID = None

    return SID


def smb4_set_system_SID(SID):
    if not SID:
        return False

    p = pipeopen("/usr/local/bin/net -d 0 setlocalsid %s" % SID)
    net_out = p.communicate()
    if p.returncode != 0:
        log.error('Failed to setlocalsid with the following error: {0}'.format(net_out[1]))
        return False
    if not net_out:
        return False

    return True


def smb4_set_domain_SID(SID):
    if not SID:
        return False

    p = pipeopen("/usr/local/bin/net -d 0 setdomainsid %s" % SID)
    net_out = p.communicate()
    if p.returncode != 0:
        log.error('Failed to setlocalsid with the following error: {0}'.format(net_out[1]))
        return False
    if not net_out:
        return False

    return True


def smb4_set_database_SID(client, SID):
    ret = False
    if not SID:
        return ret

    try:
        cifs = Struct(client.call('datastore.query', 'services.cifs', None, {'get': True}))
        client.call('datastore.update', 'services.cifs', cifs.id, {'cifs_SID': SID})
        ret = True

    except Exception as e:
        log.debug(
            'The following exception occured while trying to set database SID: {0}'.format(e)
        )
        log_traceback(log=log)
        ret = False

    return ret


def smb4_set_SID(client, role):
    get_sid_func = smb4_get_system_SID
    set_sid_func = smb4_set_system_SID

    if role == 'dc':
        get_sid_func = smb4_get_domain_SID
        set_sid_func = smb4_set_domain_SID

    database_SID = smb4_get_database_SID(client)
    system_SID = get_sid_func()

    if database_SID:
        if not system_SID:
            if not set_sid_func(database_SID):
                print("Unable to set SID to %s" % database_SID, file=sys.stderr)
        else:
            if database_SID != system_SID:
                if not set_sid_func(database_SID):
                    print(("Unable to set SID to %s" % database_SID), file=sys.stderr)

    else:
        if not system_SID:
            print(("Unable to figure out SID, things are seriously jacked!"), file=sys.stderr)

        if not set_sid_func(system_SID):
            print("Unable to set SID to %s" % system_SID, file=sys.stderr)
        else:
            smb4_set_database_SID(client, system_SID)


def smb4_ldap_enabled(client):
    ret = False

    if client.call('notifier.common', 'system', 'ldap_enabled') and client.call('notifier.common', 'system', 'ldap_has_samba_schema'):
        ret = True

    return ret


def smb4_activedirectory_enabled(client):
    ret = False

    if client.call('notifier.common', 'system', 'activedirectory_enabled'):
        ret = True

    return ret


def smb4_autorid_enabled(client):
    ret = False

    try:
        ad = Struct(client.call('datastore.query', 'directoryservice.ActiveDirectory', None, {'get': True}))
    except Exception as e:
        return ret

    if ad.ad_idmap_backend.lower() == "autorid":
        ret = True

    return ret


def config_share_for_nfs4(share):
    confset1(share, "nfs4:mode = special")
    confset1(share, "nfs4:acedup = merge")
    confset1(share, "nfs4:chown = true")


def config_share_for_zfs(share):
    confset1(share, "zfsacl:acesort = dontcare")


#
# ticket: # 16325
# aio_pthread needs to be last. But it's NOOP on FreeBSD anyhow.
# fruit needs to be before streams_xattr, streams_xattr is required
# for fruit, and if catia and fruit are used, catia comes before fruit
#
def order_vfs_objects(vfs_objects):
    vfs_objects_special = ('catia', 'zfs_space', 'zfsacl', 'fruit', 'streams_xattr', 'recycle', 'aio_pthread')
    vfs_objects_ordered = []

    if 'fruit' in vfs_objects:
        if 'streams_xattr' not in vfs_objects:
            vfs_objects.append('streams_xattr')

    for obj in vfs_objects:
        if obj not in vfs_objects_special:
            vfs_objects_ordered.append(obj)

    for obj in vfs_objects_special:
        if obj in vfs_objects:
            vfs_objects_ordered.append(obj)

    return vfs_objects_ordered


def config_share_for_vfs_objects(share, vfs_objects):
    if vfs_objects:
        vfs_objects = order_vfs_objects(vfs_objects)
        confset2(share, "vfs objects = %s", ' '.join(vfs_objects))


def extend_vfs_objects_for_zfs(path, vfs_objects):
    return

    if is_within_zfs(path):
        vfs_objects.extend([
            'zfs_space',
            'zfsacl',
        ])


def is_within_zfs(mountpoint):
    try:
        st = os.stat(mountpoint)
    except Exception as e:
        return False

    share_dev = st.st_dev

    p = pipeopen("mount")

    mount_out = p.communicate()
    if p.returncode != 0:
        return False
    if mount_out:
        mount_out = mount_out[0]

    zfs_regex = re.compile("^(.*) on (/.*) \(zfs, .*\)$")

    # The reversed is important as we would like the code to use
    # the most specific (and therefore relevant) mount point.
    for line in reversed(mount_out.split('\n')):
        match = zfs_regex.match(line.strip())
        if not match:
            continue

        mp = match.group(2)

        try:
            st = os.stat(mp)
        except Exception as e:
            continue

        if st.st_dev == share_dev:
            return True

    return False


def get_sysctl(name):
    p = pipeopen("/sbin/sysctl -n '%s'" % name)
    out = p.communicate()
    if p.returncode != 0:
        return None
    try:
        out = out[0].strip()
    except Exception as e:
        pass
    return out


def get_server_services():
    server_services = [
        'rpc', 'nbt', 'wrepl', 'ldap', 'cldap', 'kdc', 'drepl', 'winbind',
        'ntp_signd', 'kcc', 'dnsupdate', 'dns', 'smb'
    ]
    return server_services


def get_dcerpc_endpoint_servers():
    dcerpc_endpoint_servers = [
        'epmapper', 'wkssvc', 'rpcecho', 'samr', 'netlogon', 'lsarpc',
        'spoolss', 'drsuapi', 'dssetup', 'unixinfo', 'browser', 'eventlog6',
        'backupkey', 'dnsserver', 'winreg', 'srvsvc'
    ]
    return dcerpc_endpoint_servers


def get_server_role(client):
    role = "standalone"
    if client.call('notifier.common', 'system', 'activedirectory_enabled') or smb4_ldap_enabled(client):
        role = "member"

    if client.call('notifier.common', 'system', 'domaincontroller_enabled'):
        try:
            role = client.call('datastore.query', 'services.DomainController', None, {'get': True})['dc_role']
        except Exception as e:
            pass

    return role


def get_cifs_homedir(client):
    cifs_homedir = "/home"

    shares = client.call('datastore.query', 'sharing.CIFS_Share')
    if len(shares) == 0:
        return

    for share in shares:
        share = Struct(share)
        if share.cifs_home and share.cifs_path:
            cifs_homedir = share.cifs_path
            break

    return cifs_homedir


def confset1(conf, line, space=4):
    if line:
        conf.append(' ' * space + line)


def confset2(conf, line, var, space=4):
    if line and var:
        line = ' ' * space + line
        conf.append(line % var)


def configure_idmap_ad(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_ad_range_low,
        idmap.idmap_ad_range_high
    ))
    confset1(smb4_conf, "idmap config %s: schema mode = %s" % (
        domain,
        idmap.idmap_ad_schema_mode
    ))
    confset1(smb4_conf, "idmap config %s: unix_primary_group = %s" % (
        domain,
        "yes" if idmap.idmap_ad_unix_primary_group else "no"
    ))
    confset1(smb4_conf, "idmap config %s: unix_nss_info = %s" % (
        domain,
        "yes" if idmap.idmap_ad_unix_nss_info else "no"
    ))


def configure_idmap_adex(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap backend = adex")
    confset1(smb4_conf, "idmap uid = %d-%d" % (
        domain,
        idmap.idmap_adex_range_low,
        idmap.idmap_adex_range_high
    ))
    confset1(smb4_conf, "idmap gid = %d-%d" % (
        domain,
        idmap.idmap_adex_range_low,
        idmap.idmap_adex_range_high
    ))


def configure_idmap_autorid(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        "*",
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        "*",
        idmap.idmap_autorid_range_low,
        idmap.idmap_autorid_range_high
    ))
    confset1(smb4_conf, "idmap config %s: rangesize = %d" % (
        "*",
        idmap.idmap_autorid_rangesize
    ))
    confset1(smb4_conf, "idmap config %s: read only = %s" % (
        "*",
        "yes" if idmap.idmap_autorid_readonly else "no"
    ))
    confset1(smb4_conf, "idmap config %s: ignore builtin = %s" % (
        "*",
        "yes" if idmap.idmap_autorid_ignore_builtin else "no"
    ))


def configure_idmap_fruit(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_fruit_range_low,
        idmap.idmap_fruit_range_high
    ))


def configure_idmap_hash(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_hash_range_low,
        idmap.idmap_hash_range_high
    ))
    confset1(smb4_conf, "idmap_hash: name_map = %s" %
             idmap.idmap_hash_range_name_map)


def configure_idmap_ldap(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_ldap_range_low,
        idmap.idmap_ldap_range_high
    ))
    if idmap.idmap_ldap_ldap_base_dn:
        confset1(smb4_conf, "idmap config %s: ldap base dn = %s" % (
            domain,
            idmap.idmap_ldap_ldap_base_dn
        ))
    if idmap.idmap_ldap_ldap_user_dn:
        confset1(smb4_conf, "idmap config %s: ldap user dn = %s" % (
            domain,
            idmap.idmap_ldap_ldap_user_dn
        ))
    if idmap.idmap_ldap_ldap_url:
        confset1(smb4_conf, "idmap config %s: ldap url = %s" % (
            domain,
            idmap.idmap_ldap_ldap_url
        ))


def configure_idmap_nss(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_nss_range_low,
        idmap.idmap_nss_range_high
    ))


def configure_idmap_rfc2307(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_rfc2307_range_low,
        idmap.idmap_rfc2307_range_high
    ))
    confset1(smb4_conf, "idmap config %s: ldap_server = %s" % (
        domain,
        idmap.idmap_rfc2307_ldap_server
    ))
    confset1(smb4_conf, "idmap config %s: bind_path_user = %s" % (
        domain,
        idmap.idmap_rfc2307_bind_path_user
    ))
    confset1(smb4_conf, "idmap config %s: bind_path_group = %s" % (
        domain,
        idmap.idmap_rfc2307_bind_path_group
    ))
    confset1(smb4_conf, "idmap config %s: user_cn = %s" % (
        domain,
        "yes" if idmap.idmap_rfc2307_user_cn else "no"
    ))
    confset1(smb4_conf, "idmap config %s: cn_realm = %s" % (
        domain,
        "yes" if idmap.idmap_rfc2307_cn_realm else "no"
    ))
    if idmap.idmap_rfc2307_ldap_domain:
        confset1(smb4_conf, "idmap config %s: ldap_domain = %s" % (
            domain,
            idmap.idmap_rfc2307_ldap_domain
        ))
    if idmap.idmap_rfc2307_ldap_url:
        confset1(smb4_conf, "idmap config %s: ldap_url = %s" % (
            domain,
            idmap.idmap_rfc2307_ldap_url
        ))
    if idmap.idmap_rfc2307_ldap_user_dn:
        confset1(smb4_conf, "idmap config %s: ldap_user_dn = %s" % (
            domain,
            idmap.idmap_rfc2307_ldap_user_dn
        ))
    if idmap.idmap_rfc2307_ldap_realm:
        confset1(smb4_conf, "idmap config %s: ldap_realm = %s" % (
            domain,
            idmap.idmap_rfc2307_ldap_realm
        ))


def idmap_backend_rfc2307(client):
    try:
        ad = Struct(client.call('datastore.query', 'directoryservice.ActiveDirectory', None, {'get': True}))
    except Exception as e:
        return False

    return ad.ad_idmap_backend == 'rfc2307'


def set_idmap_rfc2307_secret(client):
    try:
        ad = Struct(client.call('datastore.query', 'directoryservice.ActiveDirectory', None, {'get': True}))
        ad.ds_type = 1  # FIXME: DS_TYPE_ACTIVEDIRECTORY = 1
    except Exception as e:
        return False

    domain = None
    # FIXME: ad ds_type, extend model
    idmap = Struct(client.call('notifier.ds_get_idmap_object', ad.ds_type, ad.id, ad.ad_idmap_backend))

    try:
        fad = Struct(client.call('notifier.directoryservice', 'AD'))
        domain = fad.netbiosname.upper()
    except Exception as e:
        return False

    args = [
        "/usr/local/bin/net",
        "-d 0",
        "idmap",
        "secret"
    ]

    net_cmd = "%s '%s' '%s'" % (
        ' '.join(args),
        domain,
        idmap.idmap_rfc2307_ldap_user_dn_password
    )

    p = pipeopen(net_cmd, quiet=True)
    net_out = p.communicate()
    if net_out and net_out[0]:
        for line in net_out[0].split('\n'):
            if not line:
                continue
            print(line)

    ret = True
    if p.returncode != 0:
        print("Failed to set idmap secret!", file=sys.stderr)
        ret = False

    return ret


def configure_idmap_rid(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_rid_range_low,
        idmap.idmap_rid_range_high
    ))


def configure_idmap_tdb(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_tdb_range_low,
        idmap.idmap_tdb_range_high
    ))


def configure_idmap_tdb2(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_tdb2_range_low,
        idmap.idmap_tdb2_range_high
    ))
    confset1(smb4_conf, "idmap config %s: script = %s" % (
        domain,
        idmap.idmap_tdb2_script
    ))


def configure_idmap_script(smb4_conf, idmap, domain):
    confset1(smb4_conf, "idmap config %s: backend = %s" % (
        domain,
        idmap.idmap_backend_name
    ))
    confset1(smb4_conf, "idmap config %s: range = %d-%d" % (
        domain,
        idmap.idmap_script_range_low,
        idmap.idmap_script_range_high
    ))
    confset1(smb4_conf, "idmap config %s: script = %s" % (
        domain,
        idmap.idmap_script_script
    ))


IDMAP_FUNCTIONS = {
    'IDMAP_TYPE_AD': configure_idmap_ad,
    'IDMAP_TYPE_ADEX': configure_idmap_ad,
    'IDMAP_TYPE_AUTORID': configure_idmap_autorid,
    'IDMAP_TYPE_FRUIT': configure_idmap_fruit,
    'IDMAP_TYPE_HASH': configure_idmap_hash,
    'IDMAP_TYPE_LDAP': configure_idmap_ldap,
    'IDMAP_TYPE_NSS': configure_idmap_nss,
    'IDMAP_TYPE_RFC2307': configure_idmap_rfc2307,
    'IDMAP_TYPE_RID': configure_idmap_rid,
    'IDMAP_TYPE_TDB': configure_idmap_tdb,
    'IDMAP_TYPE_TDB2': configure_idmap_tdb2,
    'IDMAP_TYPE_SCRIPT': configure_idmap_script
}


def configure_idmap_backend(client, smb4_conf, idmap, domain):
    if not domain:
        domain = "*"

    try:
        idmap_str = client.call('notifier.ds_idmap_type_code_to_string', idmap.idmap_backend_type)
        IDMAP_FUNCTIONS[idmap_str](smb4_conf, idmap, domain)
    except Exception as e:
        log.warn('Failed to configure idmap', exc_info=True)
        pass


def set_ldap_password(client):
    try:
        ldap = Struct(client.call('datastore.query', 'directoryservice.LDAP', None, {'get': True}))
    except Exception as e:
        return

    if ldap.ldap_bindpw:
        p = pipeopen("/usr/local/bin/smbpasswd -w '%s'" % (
            ldap.ldap_bindpw,
        ), quiet=True)
        out = p.communicate()
        if out and out[1]:
            for line in out[1].split('\n'):
                if not line:
                    continue
                print(line)


def add_ldap_conf(client, smb4_conf):
    try:
        ldap = Struct(client.call('datastore.query', 'directoryservice.LDAP', None, {'get': True}))
        ldap.ds_type = 2  # FIXME: DS_TYPE_LDAP = 2
        cifs = Struct(client.call('smb.config'))
    except Exception as e:
        return

    confset1(smb4_conf, "security = user")

    confset1(
        smb4_conf,
        "passdb backend = ldapsam:%s://%s" % (
            "ldaps" if ldap.ldap_ssl == 'on' else "ldap",
            ldap.ldap_hostname
        )
    )

    ldap_workgroup = cifs.workgroup.upper()

    confset2(smb4_conf, "ldap admin dn = %s", ldap.ldap_binddn)
    confset2(smb4_conf, "ldap suffix = %s", ldap.ldap_basedn)
    confset2(smb4_conf, "ldap user suffix = %s", ldap.ldap_usersuffix)
    confset2(smb4_conf, "ldap group suffix = %s", ldap.ldap_groupsuffix)
    confset2(smb4_conf, "ldap machine suffix = %s", ldap.ldap_machinesuffix)
    confset2(
        smb4_conf,
        "ldap ssl = %s",
        "start tls" if (ldap.ldap_ssl == 'start_tls') else 'off'
    )

    confset1(smb4_conf, "ldap replication sleep = 1000")
    confset1(smb4_conf, "ldap passwd sync = yes")
    confset1(smb4_conf, "ldapsam:trusted = yes")

    confset2(smb4_conf, "workgroup = %s", ldap_workgroup)
    confset1(smb4_conf, "domain logons = yes")

    idmap = Struct(client.call('notifier.ds_get_idmap_object', ldap.ds_type, ldap.id, ldap.ldap_idmap_backend))
    configure_idmap_backend(client, smb4_conf, idmap, ldap_workgroup)


def add_activedirectory_conf(client, smb4_conf):
    cachedir = "/var/tmp/.cache/.samba"

    try:
        ad = Struct(client.call('datastore.query', 'directoryservice.ActiveDirectory', None, {'get': True}))
        ad.ds_type = 1  # FIXME: DS_TYPE_ACTIVEDIRECTORY = 1
    except Exception as e:
        return

    try:
        os.makedirs(cachedir)
        os.chmod(cachedir, 0o755)
    except Exception as e:
        pass

    ad_workgroup = None

    # First try to get the workgroup from LDAP. If that fails, automatically generate based on ad_domainname
    # This is to allow us to generate a functional config even if a DC isn't available when we're generating the config
    try:
        fad = Struct(client.call('notifier.directoryservice', 'AD'))
        ad_workgroup = fad.netbiosname.upper()
    except Exception as e:
        ad_workgroup = ad.ad_domainname.upper().split(".")[0]

    confset2(smb4_conf, "workgroup = %s", ad_workgroup)
    confset2(smb4_conf, "realm = %s", ad.ad_domainname.upper())
    confset1(smb4_conf, "security = ADS")
    confset1(smb4_conf, "client use spnego = yes")

    confset1(smb4_conf, "local master = no")
    confset1(smb4_conf, "domain master = no")
    confset1(smb4_conf, "preferred master = no")

    confset2(smb4_conf, "ads dns update = %s",
             "yes" if ad.ad_allow_dns_updates else "no")

    confset1(smb4_conf, "winbind cache time = 7200")
    confset1(smb4_conf, "winbind offline logon = yes")
    confset1(smb4_conf, "winbind enum users = yes")
    confset1(smb4_conf, "winbind enum groups = yes")
    confset1(smb4_conf, "winbind nested groups = yes")
    confset2(smb4_conf, "winbind use default domain = %s",
             "yes" if ad.ad_use_default_domain else "no")
    confset1(smb4_conf, "winbind refresh tickets = yes")

    if ad.ad_nss_info:
        confset2(smb4_conf, "winbind nss info = %s", ad.ad_nss_info)

    idmap = Struct(client.call('notifier.ds_get_idmap_object', ad.ds_type, ad.id, ad.ad_idmap_backend))
    configure_idmap_backend(client, smb4_conf, idmap, ad_workgroup)

    confset2(smb4_conf, "allow trusted domains = %s",
             "yes" if ad.ad_allow_trusted_doms else "no")

    confset2(smb4_conf, "client ldap sasl wrapping = %s",
             ad.ad_ldap_sasl_wrapping)

    confset1(smb4_conf, "template shell = /bin/sh")
    cifs_homedir = "%s/%%D/%%U" % get_cifs_homedir(client)
    confset2(smb4_conf, "template homedir = %s", cifs_homedir)


def add_domaincontroller_conf(client, smb4_conf):
    try:
        dc = Struct(client.call('datastore.query', 'services.DomainController', None, {'get': True}))
        cifs = Struct(client.call('smb.config'))
    except Exception as e:
        return

    # server_services = get_server_services()
    # dcerpc_endpoint_servers = get_dcerpc_endpoint_servers()

    confset2(smb4_conf, "netbios name = %s", cifs.netbiosname.upper())
    if cifs.netbiosalias:
        confset2(smb4_conf, "netbios aliases = %s", cifs.netbiosalias.upper())
    confset2(smb4_conf, "workgroup = %s", dc.dc_domain.upper())
    confset2(smb4_conf, "realm = %s", dc.dc_realm)
    confset2(smb4_conf, "dns forwarder = %s", dc.dc_dns_forwarder)
    confset1(smb4_conf, "idmap_ldb:use rfc2307 = yes")

    # We have to manually add vfs objects here until we get more general fix to DC
    # code in loadparm.c
    confset1(smb4_conf, "vfs objects = dfs_samba4 zfsacl")

    # confset2(smb4_conf, "server services = %s",
    #    string.join(server_services, ',').rstrip(','))
    # confset2(smb4_conf, "dcerpc endpoint servers = %s",
    #    string.join(dcerpc_endpoint_servers, ',').rstrip(','))

    ipv4_addrs = []
    if cifs.bindip:
        for i in cifs.bindip:
            try:
                socket.inet_aton(i)
                ipv4_addrs.append(i)
            except Exception as e:
                pass

    else:
        interfaces = client.call('notifier.choices', 'IPChoices', [True, False])
        for i in interfaces:
            try:
                socket.inet_aton(i[0])
                ipv4_addrs.append(i[0])
            except Exception as e:
                pass

    with open("/usr/local/etc/lmhosts", "w") as f:
        for ipv4 in ipv4_addrs:
            f.write("%s\t%s\n" % (ipv4, dc.dc_domain.upper()))


def get_smb4_users(client):
    return client.call('datastore.query', 'account.bsdusers', [
        ['OR', [
            ('bsdusr_smbhash', '~', r'^.+:.+:[X]{32}:.+$'),
            ('bsdusr_smbhash', '~', r'^.+:.+:[A-F0-9]{32}:.+$'),
        ]],
    ])


def get_disabled_users(client):
    # XXX: WTF moment, this method is not used
    disabled_users = []
    try:
        # FIXME: test query and support for OR
        users = client.call('datastore.query', 'account.bsdusers', (
            ('bsdusr_smbhash', '~', r'^.+:.+:XXXX.+$'),
            (
                'OR',
                ('bsdusr_locked', '=', True),
                ('bsdusr_password_disabled', '=', True),
            ),
        ))
        for u in users:
            disabled_users.append(u)

    except Exception as e:
        disabled_users = []

    return disabled_users


def generate_smb4_tdb(client, smb4_tdb):
    try:
        users = get_smb4_users(client)
        for u in users:
            smb4_tdb.append(u['bsdusr_smbhash'])
    except Exception as e:
        return


def generate_smb4_conf(client, smb4_conf, role):
    cifs = Struct(client.call('smb.config'))

    if not cifs.guest:
        cifs.guest = 'ftp'
    if not cifs.filemask:
        cifs.filemask = "0666"
    if not cifs.dirmask:
        cifs.dirmask = "0777"

    # standard stuff... should probably do this differently
    confset1(smb4_conf, "[global]", space=0)

    if os.path.exists("/usr/local/etc/smbusers"):
        confset1(smb4_conf, "username map = /usr/local/etc/smbusers")

    if not cifs.enable_smb1:
        confset1(smb4_conf, "server min protocol = SMB2_02")
    else:
        confset1(smb4_conf, "server min protocol = NT1")

    server_max_protocol = fs().services.smb.config.server_max_protocol
    if server_max_protocol != 'NONE':
        confset2(smb4_conf, "server max protocol = %s", server_max_protocol)

    server_multi_channel = fs().services.smb.config.server_multi_channel
    if server_multi_channel != 0:
        confset1(smb4_conf, "server multi channel support = yes")

    if cifs.bindip:
        interfaces = []

        bindips = ' '.join(cifs.bindip)
        if role != 'dc':
            bindips = "127.0.0.1 %s" % bindips

        bindips = bindips.split()
        for bindip in bindips:
            if not bindip:
                continue
            bindip = bindip.strip()
            iface = client.call('notifier.get_interface', bindip)

            is_carp_interface = False
            if iface:
                try:
                    is_carp_interface = client.call('notifier.is_carp_interface', iface)
                except Exception as e:
                    pass

            if iface and is_carp_interface:
                parent_iface = client.call('notifier.get_parent_interface', iface)
                if not parent_iface:
                    continue

                parent_iinfo = client.call('notifier.get_interface_info', parent_iface[0])
                if not parent_iinfo:
                    continue

                interfaces.append("%s/%s" % (bindip, parent_iface[2]))
            else:
                interfaces.append(bindip)

        if interfaces:
            confset2(smb4_conf, "interfaces = %s", ' '.join(interfaces))
        confset1(smb4_conf, "bind interfaces only = yes")

    confset1(smb4_conf, "encrypt passwords = yes")
    confset1(smb4_conf, "dns proxy = no")
    confset1(smb4_conf, "strict locking = no")
    confset1(smb4_conf, "oplocks = yes")
    confset1(smb4_conf, "deadtime = 15")
    confset1(smb4_conf, "max log size = 51200")

    if truenas_params['is_truenas_ha'] and truenas_params['smb_ha_mode'] == 'LEGACY':
        confset1(smb4_conf, "private dir = /root/samba/private")
    else:
        confset1(smb4_conf, "private dir = /var/db/samba4/private")

    confset2(smb4_conf, "max open files = %d",
             int(get_sysctl('kern.maxfilesperproc')) - 25)

    if cifs.loglevel and cifs.loglevel is not True:
        loglevel = cifs.loglevel
    else:
        loglevel = "0"

    if cifs.syslog:
        confset1(smb4_conf, "logging = syslog:%s" % loglevel)
    else:
        confset1(smb4_conf, "logging = file")

    if truenas_params['is_truenas_ha'] and truenas_params['smb_ha_mode'] == 'LEGACY':
        confset1(smb4_conf, "winbind netbios alias spn = false")

    confset1(smb4_conf, "load printers = no")
    confset1(smb4_conf, "printing = bsd")
    confset1(smb4_conf, "printcap name = /dev/null")
    confset1(smb4_conf, "disable spoolss = yes")
    confset1(smb4_conf, "getwd cache = yes")
    confset1(smb4_conf, "cache directory = /var/lock")
    confset2(smb4_conf, "guest account = %s", cifs.guest)
    confset1(smb4_conf, "map to guest = Bad User")
    confset2(smb4_conf, "obey pam restrictions = %s",
             "yes" if cifs.obey_pam_restrictions else "no")
    confset2(smb4_conf, "ntlm auth = %s",
             "yes" if cifs.ntlmv1_auth else "no")
    confset1(smb4_conf, "directory name cache size = 0")
    confset1(smb4_conf, "kernel change notify = no")

    confset1(smb4_conf,
             "panic action = /usr/local/libexec/samba/samba-backtrace")
    confset1(smb4_conf, "nsupdate command = /usr/local/bin/samba-nsupdate -g")

    confset2(smb4_conf, "server string = %s", cifs.description)
    confset1(smb4_conf, "ea support = yes")
    confset1(smb4_conf, "store dos attributes = yes")
    confset1(smb4_conf, "lm announce = yes")
    confset2(smb4_conf, "hostname lookups = %s",
             "yes" if cifs.hostlookup else False)
    confset2(smb4_conf, "unix extensions = %s",
             "no" if not cifs.unixext else False)
    confset2(smb4_conf, "time server = %s",
             "yes" if cifs.timeserver else False)
    confset2(smb4_conf, "null passwords = %s",
             "yes" if cifs.nullpw else False)
    confset2(smb4_conf, "acl allow execute always = %s",
             "true" if cifs.allow_execute_always else "false")
    confset1(smb4_conf, "dos filemode = yes")
    confset2(smb4_conf, "multicast dns register = %s",
             "yes" if cifs.zeroconf else "no")

    if not smb4_ldap_enabled(client):
        confset2(smb4_conf, "domain logons = %s",
                 "yes" if cifs.domain_logons else "no")

    if not client.call('notifier.common', 'system', 'activedirectory_enabled'):
        confset2(smb4_conf, "local master = %s",
                 "yes" if cifs.localmaster else "no")

    if not smb4_autorid_enabled(client):
        # 5 = DS_TYPE_CIFS
        idmap = Struct(client.call('notifier.ds_get_idmap_object', 5, cifs.id, 'tdb'))
        configure_idmap_backend(client, smb4_conf, idmap, None)

    if role == 'auto':
        confset1(smb4_conf, "server role = auto")

    elif role == 'classic':
        confset1(smb4_conf, "server role = classic primary domain controller")

    elif role == 'netbios':
        confset1(smb4_conf, "server role = netbios backup domain controller")

    elif role == 'dc':
        confset1(smb4_conf, "server role = active directory domain controller")
        add_domaincontroller_conf(client, smb4_conf)

    elif role == 'member':
        confset1(smb4_conf, "server role = member server")

        if smb4_ldap_enabled(client):
            add_ldap_conf(client, smb4_conf)

        elif client.call('notifier.common', 'system', 'activedirectory_enabled'):
            add_activedirectory_conf(client, smb4_conf)

        confset2(smb4_conf, "netbios name = %s", cifs.netbiosname.upper())
        if cifs.netbiosalias:
            confset2(smb4_conf, "netbios aliases = %s", cifs.netbiosalias.upper())

    elif role == 'standalone':
        confset1(smb4_conf, "server role = standalone")
        confset2(smb4_conf, "netbios name = %s", cifs.netbiosname.upper())
        if cifs.netbiosalias:
            confset2(smb4_conf, "netbios aliases = %s", cifs.netbiosalias.upper())
        confset2(smb4_conf, "workgroup = %s", cifs.workgroup.upper())
        confset1(smb4_conf, "security = user")

    confset2(smb4_conf, "create mask = %s", cifs.filemask)
    confset2(smb4_conf, "directory mask = %s", cifs.dirmask)
    confset2(smb4_conf, "client ntlmv2 auth = %s",
             "yes" if not cifs.ntlmv1_auth else "no")
    confset2(smb4_conf, "dos charset = %s", cifs.doscharset)
    confset2(smb4_conf, "unix charset = %s", cifs.unixcharset)

    if cifs.loglevel and cifs.loglevel is not True:
        confset2(smb4_conf, "log level = %s", cifs.loglevel)

    smb_options = cifs.smb_options.strip()
    for line in smb_options.split('\n'):
        line = line.strip()
        if not line:
            continue
        confset1(smb4_conf, line)


def generate_smb4_shares(client, smb4_shares):
    shares = client.call('datastore.query', 'sharing.CIFS_Share')

    if len(shares) == 0:
        return

    for share in shares:
        share = Struct(share)
        if (not share.cifs_home and
                not os.path.isdir(share.cifs_path)):
            continue

        confset1(smb4_shares, "\n")
        if share.cifs_home:
            confset1(smb4_shares, "[homes]", space=0)

            valid_users_path = "%U"
            valid_users = "%U"

            if client.call('notifier.common', 'system', 'activedirectory_enabled'):
                valid_users_path = "%D/%U"
                valid_users = "%D\%U"

                try:
                    ad = Struct(client.call('notifier.directoryservice', 'AD'))
                    for w in ad.workgroups:
                        homedir_path = "%s/%s" % (share.cifs_path, w)
                        if not os.access(homedir_path, os.F_OK):
                            smb4_mkdir(homedir_path)

                except Exception as e:
                    pass

            confset2(smb4_shares, "valid users = %s", valid_users)

            if share.cifs_path:
                cifs_homedir_path = ("%s/%s" %
                                     (share.cifs_path, valid_users_path))
                confset2(smb4_shares, "path = %s", qw(cifs_homedir_path))
            if share.cifs_comment:
                confset2(smb4_shares,
                         "comment = %s", share.cifs_comment)
            else:
                confset1(smb4_shares, "comment = Home Directories")
        else:
            confset2(smb4_shares, "[%s]", share.cifs_name, space=0)
            confset2(smb4_shares, "path = %s", qw(share.cifs_path))
            confset2(smb4_shares, "comment = %s", share.cifs_comment)
        confset1(smb4_shares, "printable = no")
        confset1(smb4_shares, "veto files = /.snapshot/.windows/.mac/.zfs/")
        confset2(smb4_shares, "writeable = %s",
                 "no" if share.cifs_ro else "yes")
        confset2(smb4_shares, "browseable = %s",
                 "yes" if share.cifs_browsable else "no")
        confset2(smb4_shares, "access based share enum = %s",
                 "yes" if share.cifs_abe else "no")

        task = None
        if share.cifs_storage_task:
            task = share.cifs_storage_task

        vfs_objects = []
        if task:
            vfs_objects.append('shadow_copy2')
        extend_vfs_objects_for_zfs(share.cifs_path, vfs_objects)
        vfs_objects.extend(share.cifs_vfsobjects)

        if share.cifs_recyclebin:
            vfs_objects.append('recycle')
            confset1(smb4_shares, "recycle:repository = .recycle/%U")
            confset1(smb4_shares, "recycle:keeptree = yes")
            confset1(smb4_shares, "recycle:versions = yes")
            confset1(smb4_shares, "recycle:touch = yes")
            confset1(smb4_shares, "recycle:directory_mode = 0777")
            confset1(smb4_shares, "recycle:subdir_mode = 0700")

        if task:
            confset1(smb4_shares, "shadow:snapdir = .zfs/snapshot")
            confset1(smb4_shares, "shadow:sort = desc")
            confset1(smb4_shares, "shadow:localtime = yes")
            confset1(smb4_shares,
                     "shadow:format = auto-%%Y%%m%%d.%%H%%M-%s%s" %
                     (task.task_ret_count, task.task_ret_unit[0]))
            confset1(smb4_shares, "shadow:snapdirseverywhere = yes")

        config_share_for_vfs_objects(smb4_shares, vfs_objects)

        confset2(smb4_shares, "hide dot files = %s",
                 "no" if share.cifs_showhiddenfiles else "yes")
        confset2(smb4_shares, "hosts allow = %s", share.cifs_hostsallow)
        confset2(smb4_shares, "hosts deny = %s", share.cifs_hostsdeny)
        confset2(smb4_shares, "guest ok = %s",
                 "yes" if share.cifs_guestok else "no")

        confset2(smb4_shares, "guest only = %s",
                 "yes" if share.cifs_guestonly else False)

        config_share_for_nfs4(smb4_shares)
        config_share_for_zfs(smb4_shares)

        for line in share.cifs_auxsmbconf.split('\n'):
            line = line.strip()
            if not line:
                continue
            confset1(smb4_shares, line)


def generate_smb4_system_shares(client, smb4_shares):
    if client.call('notifier.common', 'system', 'domaincontroller_enabled'):
        try:
            dc = Struct(client.call('datastore.query', 'services.DomainController', None, {'get': True}))
            sysvol_path = "/var/db/samba4/sysvol"

            for share in ["sysvol", "netlogon"]:
                confset1(smb4_shares, "\n")
                confset1(smb4_shares, "[%s]" % (share), space=0)

                if share == "sysvol":
                    path = sysvol_path
                else:
                    path = "%s/%s/scripts" % (sysvol_path, dc.dc_realm.lower())

                confset1(smb4_shares, "path = %s" % (path))
                confset1(smb4_shares, "read only = no")
                # map_dacl_protected=true and nfs4:mode=simple are required
                # to pass samba-tool ACL validation on GPOs
                confset1(smb4_shares, "zfsacl:map_dacl_protected=true")
                confset1(smb4_shares, "nfs4:mode=simple")
                confset1(smb4_shares, "nfs4:chown=true")

                config_share_for_zfs(smb4_shares)

        except Exception as e:
            pass


def generate_smbusers(client):
    # FIXME: test query
    users = client.call('datastore.query', 'account.bsdusers', [
        ('bsdusr_microsoft_account', '=', True),
        ('bsdusr_email', '!=', None),
        ('bsdusr_email', '!=', ''),
    ])
    if not users:
        return

    with open("/usr/local/etc/smbusers", "w") as f:
        for u in users:
            u = Struct(u)
            f.write("%s = %s\n" % (u.bsdusr_username, u.bsdusr_email))
    os.chmod("/usr/local/etc/smbusers", 0o644)


def provision_smb4(client):
    if not client.call('notifier.samba4', 'domain_provision', timeout=300):
        print("Failed to provision domain", file=sys.stderr)
        return False

    if not client.call('notifier.samba4', 'disable_password_complexity'):
        print("Failed to disable password complexity", file=sys.stderr)
        return False

    if not client.call('notifier.samba4', 'set_min_pwd_length'):
        print("Failed to set minimum password length", file=sys.stderr)
        return False

    if not client.call('notifier.samba4', 'set_administrator_password'):
        print("Failed to set administrator password", file=sys.stderr)
        return False

    if not client.call('notifier.samba4', 'domain_sentinel_file_create'):
        return False

    return True


def smb4_mkdir(dir):
    try:
        os.makedirs(dir)
    except Exception as e:
        pass


def smb4_unlink(dir):
    try:
        os.unlink(dir)
    except Exception as e:
        pass


def smb4_setup(client):
    statedir = "/var/db/samba4"
    privatedir = "/var/db/samba4/private"

    if truenas_params['is_truenas_ha'] and truenas_params['smb_ha_mode'] == "LEGACY":
        privatedir = "/root/samba/private"

    if not os.access(privatedir, os.F_OK):
        smb4_mkdir(privatedir)
        os.chmod(privatedir, 0o700)

    smb4_mkdir("/var/run/samba")
    smb4_mkdir("/var/run/samba4")

    smb4_mkdir("/var/log/samba4")
    os.chmod("/var/log/samba4", 0o755)

    smb4_unlink("/usr/local/etc/smb.conf")
    smb4_unlink("/usr/local/etc/smb4.conf")

    if truenas_params['failover_status'] == 'BACKUP':
        return

    systemdataset = client.call('systemdataset.config')

    if not systemdataset['is_decrypted']:
        if os.path.islink(statedir):
            smb4_unlink(statedir)
            smb4_mkdir(statedir)
        return

    systemdataset_path = systemdataset['path'] or statedir

    basename_realpath = os.path.join(systemdataset_path, 'samba4')
    statedir_realpath = os.path.realpath(statedir)

    if os.path.islink(statedir) and not os.path.exists(statedir):
        smb4_unlink(statedir)

    if (basename_realpath != statedir_realpath and
            os.path.exists(basename_realpath)):
        smb4_unlink(statedir)
        if os.path.exists(statedir):
            olddir = "%s.%s" % (statedir, time.strftime("%Y%m%d%H%M%S"))
            try:
                os.rename(statedir, olddir)
            except Exception as e:
                print("Unable to rename '%s' to '%s' (%s)" % (
                    statedir, olddir, e), file=sys.stderr)
                sys.exit(1)

        try:
            os.symlink(basename_realpath, statedir)
        except Exception as e:
            print(("Unable to create symlink '%s' -> '%s' (%s)" % (basename_realpath, statedir, e)), file=sys.stderr)
            sys.exit(1)

    if os.path.islink(statedir) and not os.path.exists(statedir_realpath):
        smb4_unlink(statedir)
        smb4_mkdir(statedir)

    if not os.access("/var/db/samba4/private", os.F_OK):
        smb4_mkdir("/var/db/samba4/private")
        os.chmod("/var/db/samba4/private", 0o700)

    os.chmod(statedir, 0o755)


def get_old_samba4_datasets(client):
    old_samba4_datasets = []

    fsvols = client.call('notifier.list_zfs_fsvols')
    for fsvol in fsvols:
        if re.match('^.+/.samba4\/?$', fsvol):
            old_samba4_datasets.append(fsvol)

    return old_samba4_datasets


def migration_available(old_samba4_datasets):
    res = False

    if old_samba4_datasets and len(old_samba4_datasets) == 1:
        res = True
    elif old_samba4_datasets:
        with open("/var/db/samba4/.alert_cant_migrate", "w") as f:
            f.close()

    return res


def do_migration(client, old_samba4_datasets):
    if len(old_samba4_datasets) > 1:
        return False
    old_samba4_dataset = "/mnt/%s/" % old_samba4_datasets[0]

    try:
        pipeopen("/usr/local/bin/rsync -avz '%s'* '/var/db/samba4/'" %
                 old_samba4_dataset).wait()
        client.call('notifier.destroy_zfs_dataset', old_samba4_datasets[0], True)

    except Exception as e:
        print(e, file=sys.stderr)

    return True


def smb4_import_users(client, smb_conf_path, smb4_tdb, exportfile=None):
    f = tempfile.NamedTemporaryFile(mode='w+', dir="/tmp")
    for line in smb4_tdb:
        f.write(line + '\n')
    f.flush()

    args = [
        "/usr/local/bin/pdbedit",
        "-d 0",
        "-i smbpasswd:%s" % f.name,
        "-s %s" % smb_conf_path
    ]

    if exportfile is not None:
        # smb4_unlink(exportfile)
        args.append("-e tdbsam:%s" % exportfile)

    p = pipeopen(' '.join(args))
    pdbedit_out = p.communicate()
    if pdbedit_out and pdbedit_out[0]:
        for line in pdbedit_out[0].split('\n'):
            line = line.strip()
            if not line:
                continue
            print(line)

    f.close()
    smb4_users = get_smb4_users(client)
    for u in smb4_users:
        u = Struct(u)
        smbhash = u.bsdusr_smbhash
        parts = smbhash.split(':')
        user = parts[0]

        flags = "-e"
        if u.bsdusr_locked or u.bsdusr_password_disabled:
            flags = "-d"

        p = pipeopen("/usr/local/bin/smbpasswd %s '%s'" % (flags, user))
        smbpasswd_out = p.communicate()

        if p.returncode != 0:
            print("Failed to disable %s" % user, file=sys.stderr)
            continue

        if smbpasswd_out and smbpasswd_out[0]:
            for line in smbpasswd_out[0].split('\n'):
                line = line.strip()
                if not line:
                    continue
                print(line)


def smb4_grant_user_rights(user):
    args = [
        "/usr/local/bin/net",
        "-d 0",
        "sam",
        "rights",
        "grant"
    ]

    rights = [
        "SeTakeOwnershipPrivilege",
        "SeBackupPrivilege",
        "SeRestorePrivilege"
    ]

    net_cmd = "%s %s %s" % (
        ' '.join(args),
        user,
        ' '.join(rights)
    )

    p = pipeopen(net_cmd)
    net_out = p.communicate()
    if net_out and net_out[0]:
        for line in net_out[0].split('\n'):
            if not line:
                continue
            print(line)

    if p.returncode != 0:
        return False

    return True


def smb4_grant_rights():
    args = [
        "/usr/local/bin/pdbedit",
        "-d 0",
        "-L"
    ]

    p = pipeopen(' '.join(args))
    pdbedit_out = p.communicate()
    if pdbedit_out and pdbedit_out[0]:
        for line in pdbedit_out[0].split('\n'):
            if not line:
                continue

            parts = line.split(':')
            user = parts[0]
            smb4_grant_user_rights(user)


def get_groups(client):
    _groups = {}

    groups = client.call('datastore.query', 'account.bsdGroups', [('bsdgrp_builtin', '=', False)])
    for g in groups:
        g = Struct(g)
        key = str(g.bsdgrp_group)
        _groups[key] = []
        members = client.call('datastore.query', 'account.bsdGroupMembership', [('bsdgrpmember_group', '=', g.id)])
        for m in members:
            m = Struct(m)
            if m.bsdgrpmember_user:
                _groups[key].append(str(m.bsdgrpmember_user.bsdusr_username))

    return _groups


def smb4_import_groups(client):
    # XXX: WTF moment, this method is not used
    groups = get_groups(client)
    for g in groups:
        client.call('notifier.samba4', 'group_add', [g])
        if groups[g]:
            client.call('notifier.samba4', 'group_addmembers', [g, groups[g]])


def smb4_group_mapped(groupmap, group):
    if not groupmap:
        return False

    for gm in groupmap:
        unixgroup = gm['unixgroup']
        if group == unixgroup:
            return True

    return False


# Windows no likey
def smb4_groupname_is_username(group):
    try:
        pwd.getpwnam(group)
    except KeyError:
        return False

    return True


def smb4_map_groups(client):
    groupmap = client.call('notifier.groupmap_list')
    groups = get_groups(client)
    for g in groups:
        if not (smb4_group_mapped(groupmap, g) or smb4_groupname_is_username(g)):
            client.call('notifier.groupmap_add', g, g)


def smb4_backup_tdbfile(tdb_src, tdb_dst):
    proc = subprocess.Popen(
        "/usr/local/bin/tdbdump {} | /usr/local/bin/tdbrestore {}".format(
            tdb_src,
            tdb_dst,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        encoding='utf8',
    )
    err = proc.communicate()[1]
    if proc.returncode != 0:
        log.error("Failed to dump and restore tdb: {}".format(err))
        log_traceback(log=log)
        return False

    if os.path.exists(tdb_dst):
        os.chmod(tdb_dst, 0o600)

    return True


def smb4_restore_tdbfile(tdb_src, tdb_dst):
    proc = subprocess.Popen(
        "/usr/local/bin/tdbdump {} | /usr/local/bin/tdbrestore {}".format(
            tdb_src,
            tdb_dst,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        encoding='utf8',
    )
    err = proc.communicate()[1]
    if proc.returncode != 0:
        log.error("Failed to dump and restore tdb: {}".format(err))
        log_traceback(log=log)
        return False
    return True


def backup_secrets_database():
    secrets = '/var/db/samba4/private/secrets.tdb'
    backup = '/root/secrets.tdb'

    if os.path.exists(secrets):
        smb4_backup_tdbfile(secrets, backup)


def restore_secrets_database():
    secrets = '/var/db/samba4/private/secrets.tdb'
    backup = '/root/secrets.tdb'

    smb4_restore_tdbfile(backup, secrets)


def smb4_do_migrations(client):
    sentinel_directory = "/data/sentinels/samba"

    if not os.access(sentinel_directory, os.F_OK):
        smb4_mkdir(sentinel_directory)
        os.chmod(sentinel_directory, 0o700)

    # 11.1-U3 -> 11.1-U4
    def migrate_11_1_U3_to_11_1_U4(client):
        samba_user_import_file = "/var/db/samba4/.usersimported"
        sentinel_file = os.path.join(sentinel_directory, "private-dir-fix")

        if not os.access(sentinel_file, os.F_OK):
            if os.access(samba_user_import_file, os.F_OK):
                os.unlink(samba_user_import_file)
            open(sentinel_file, "w").close()

    migrate_11_1_U3_to_11_1_U4(client)


def generate_global_stub(cifs, failover_status):
    if failover_status != "MASTER":
        with open("/usr/local/etc/smb4.conf", "w") as f:
            f.write("[global]\n")
            f.write(f"netbios name = {cifs['netbiosname']}_PASSIVE\n")
            f.write("multicast dns register = False\n")
            f.write("logging = file\n")


def main():
    smb4_tdb = []
    smb4_conf = []
    smb4_shares = []

    smb_conf_path = "/usr/local/etc/smb4.conf"

    client = Client()

    if not client.call('notifier.is_freenas') and client.call('notifier.failover_licensed'):
        truenas_params['is_truenas_ha'] = True
        truenas_params['failover_status'] = client.call('notifier.failover_status')
        systemdataset = client.call('systemdataset.config')
        cifs = client.call('smb.config')
        if systemdataset['pool'] is not 'freenas-boot' and cifs['netbiosname'] == cifs['netbiosname_b']:
            truenas_params['smb_ha_mode'] = 'UNIFIED'
            if truenas_params['failover_status'] != "MASTER":
                """
                   In this case we only need a stub of an smb4.conf file.
                   at some point in the future we can transition to not running samba on the passive,
                   but the stub configuration is useful in case the service gets accidentally started.
                """
                generate_global_stub(cifs)
                return

    privatedir = "/var/db/samba4/private"
    if truenas_params['is_truenas_ha'] and truenas_params['smb_ha_mode'] == 'LEGACY':
        privatedir = "/root/samba/private"

    smb4_setup(client)
    smb4_do_migrations(client)

    old_samba4_datasets = get_old_samba4_datasets(client)
    if migration_available(old_samba4_datasets):
        do_migration(client, old_samba4_datasets)

    role = get_server_role(client)

    generate_smbusers(client)
    generate_smb4_tdb(client, smb4_tdb)
    generate_smb4_conf(client, smb4_conf, role)
    generate_smb4_system_shares(client, smb4_shares)
    generate_smb4_shares(client, smb4_shares)

    if role == 'dc' and not client.call('notifier.samba4', 'domain_provisioned'):
        provision_smb4(client)

    with open(smb_conf_path, "w") as f:
        for line in smb4_conf:
            f.write(line + '\n')
        for line in smb4_shares:
            f.write(line + '\n')

    smb4_set_SID(client, role)

    if role == 'member' and smb4_ldap_enabled(client):
        set_ldap_password(client)

    if role != 'dc':
        if not client.call('notifier.samba4', 'users_imported'):
            smb4_import_users(
                client,
                smb_conf_path,
                smb4_tdb,
                privatedir + "/passdb.tdb"
            )
            if role != 'member':
                smb4_grant_rights()

            client.call('notifier.samba4', 'user_import_sentinel_file_create')

        smb4_map_groups(client)

    if role == 'member' and client.call('notifier.common', 'system', 'activedirectory_enabled') and idmap_backend_rfc2307(client):
        set_idmap_rfc2307_secret(client)


if __name__ == '__main__':
    main()
