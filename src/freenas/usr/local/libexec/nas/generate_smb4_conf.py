#!/usr/local/bin/python

from middlewared.client import Client
from middlewared.client.utils import Struct
from middlewared.plugins.smb import LOGLEVEL_MAP

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

from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.log import log_traceback
from freenasUI.common.freenassysctl import freenas_sysctl as fs

log = logging.getLogger('generate_smb4_conf')

is_truenas_ha = False


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

    if not os.access(privatedir, os.F_OK):
        smb4_mkdir(privatedir)
        os.chmod(privatedir, 0o700)

    smb4_mkdir("/var/run/samba")
    smb4_mkdir("/var/run/samba4")
    smb4_mkdir("/root/samba/private")

    smb4_mkdir("/var/log/samba4")
    os.chmod("/var/log/samba4", 0o755)

    smb4_unlink("/usr/local/etc/smb.conf")
    smb4_unlink("/usr/local/etc/smb4.conf")

    if not client.call('notifier.is_freenas') and client.call('notifier.failover_status') == 'BACKUP':
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


def smb4_is_disallowed_group(groupmap, group):
    disallowed_list = []
    # Ticket # 23435 In order for local groups to be available through samba, they need to
    # be properly mapped to NT groups in the group_mapping.tdb file. This file should:
    # (1) contain no duplicate or inconsistent entries
    # (2) contain no group names that are identical to usernames
    # (3) prevent duplicate entries for NT names associated with builtin/well-known sids.

    default_builtin_groups = ['Users', 'Administrators']
    localusers = list(pwd.getpwall())
    for localuser in localusers:
        disallowed_list.append(localuser[0].upper())
    for default_builtin_group in default_builtin_groups:
        disallowed_list.append(default_builtin_group.upper())
    for gm in groupmap:
        disallowed_list.append(gm['unixgroup'].upper())

    if group.upper() in disallowed_list:
        return True

    return False


def smb4_map_groups(client):
    groupmap = client.call('notifier.groupmap_list')
    groups = get_groups(client)
    for g in groups:
        if not (smb4_is_disallowed_group(groupmap, g)):
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


def main():
    smb4_tdb = []
    smb4_conf = []
    smb4_shares = []

    smb_conf_path = "/usr/local/etc/smb4.conf"

    client = Client()

    smb4_setup(client)
    smb4_do_migrations(client)

    old_samba4_datasets = get_old_samba4_datasets(client)
    if migration_available(old_samba4_datasets):
        do_migration(client, old_samba4_datasets)

    role = get_server_role(client)

    generate_smbusers(client)
    generate_smb4_tdb(client, smb4_tdb)

    if role == 'dc' and not client.call('notifier.samba4', 'domain_provisioned'):
        provision_smb4(client)

    client.call('etc.generate', 'smb')
    client.call('etc.generate', 'smb_share')

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

            client.call('notifier.samba4', 'user_import_sentinel_file_create')

        smb4_map_groups(client)

    if role == 'member' and client.call('notifier.common', 'system', 'activedirectory_enabled') and idmap_backend_rfc2307(client):
        set_idmap_rfc2307_secret(client)


if __name__ == '__main__':
    main()
