#!/usr/local/bin/python

import os
import re
import sys
import tempfile
import time

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from django.db.models import Q

from freenasUI.account.models import bsdUsers
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.samba import Samba4
from freenasUI.common.system import get_samba4_path
from freenasUI.middleware.notifier import notifier
from freenasUI.services.models import (
    services,
    ActiveDirectory,
    CIFS,
    DomainController,
    LDAP,
    NT4
)

from freenasUI.sharing.models import CIFS_Share
from freenasUI.storage.models import Task
from freenasUI.system.models import Settings


def is_within_zfs(mountpoint):
    try:
        st = os.stat(mountpoint)
    except:
        return False

    share_dev = st.st_dev
    p = pipeopen("zfs list -H -o mountpoint")
    zfsout = p.communicate()
    if p.returncode != 0:
        return False
    if zfsout:
        zfsout = zfsout[0]

    for mp in zfsout.split('\n'):
        mp = mp.strip()
        if mp == '-':
            continue

        try:
            st = os.stat(mp)
        except:
            continue

        if st.st_dev == share_dev:
            return True

    return False


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


def directoryservice_enabled(ds=None):
    enabled = False
    if not ds:
        return enabled

    try:
        if services.objects.filter(srv_service='directoryservice')[0].srv_enable:
            settings = Settings.objects.all()[0]
            if settings.stg_directoryservice == ds:
                enabled = True
    except:
        pass

    return enabled


def activedirectory_enabled():
    return directoryservice_enabled('activedirectory')


def domaincontroller_enabled():
    return directoryservice_enabled('domaincontroller')


def ldap_enabled():
    return directoryservice_enabled('ldap')


def nis_enabled():
    return directoryservice_enabled('nis')


def nt4_enabled():
    return directoryservice_enabled('nt4')


def get_server_role():
    role = "standalone"
    if nt4_enabled() or activedirectory_enabled() or ldap_enabled():
        role = "member"

    if domaincontroller_enabled():
        try:
            dc = DomainController.objects.all()[0]
            role = dc.dc_role
        except:
            pass

    return role


def confset1(conf, line, space=4):
    if not line:
        return

    i = 0
    str = ''
    while i < space:
        str += ' '
        i += 1
    line = str + line

    conf.append(line)


def confset2(conf, line, var, space=4):
    if not line:
        return

    i = 0
    str = ''
    while i < space:
        str += ' '
        i += 1
    line = str + line

    if var:
        conf.append(line % var)


def add_nt4_conf(smb4_conf):
    try:
        nt4 = NT4.objects.all()[0]
    except:
        return

    with open("/usr/local/etc/lmhosts", "w") as f:
        f.write("%s\t%s\n" % (nt4.nt4_dcname, nt4.nt4_workgroup.upper()))
        f.close()

    confset2(smb4_conf, "netbios name = %s", nt4.nt4_netbiosname.upper())
    confset2(smb4_conf, "workgroup = %s", nt4.nt4_workgroup.upper())

    confset1(smb4_conf, "security = domain")
    confset1(smb4_conf, "password server = *")

    confset1(smb4_conf, "winbind uid = 10000-20000")
    confset1(smb4_conf, "winbind gid = 10000-20000")
    confset1(smb4_conf, "winbind enum users = yes")
    confset1(smb4_conf, "winbind enum groups = yes")
    confset1(smb4_conf, "template shell = /bin/sh")

    confset1(smb4_conf, "local master = no")
    confset1(smb4_conf, "domain master = no")
    confset1(smb4_conf, "preferred master = no")


def add_ldap_conf(smb4_conf):
    try:
        ldap = LDAP.objects.all()[0]
        cifs = CIFS.objects.all()[0]
    except:
        return

    confset1(smb4_conf, "security = user")

    confset2(
        smb4_conf,
        "passdb backend = %s",
        "ldapsam:ldaps://%s" % ldap.ldap_hostname if \
        (ldap.ldap_ssl == 'on' or ldap.ldap_ssl == 'start_tls') else
        "ldapsam:ldap://%s" % ldap.ldap_hostname
    )

    confset2(smb4_conf, "ldap admin dn = %s", ldap.ldap_rootbasedn)

    if ldap.ldap_rootbindpw:
        p = pipeopen("/usr/local/bin/smbpasswd -w '%s'" % ldap.ldap_rootbindpw)
        out = p.communicate()
        if out and out[1]:
            for line in out[1].split('\n'):
                print line

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
    confset1(smb4_conf, "idmap uid = 10000-39999")
    confset1(smb4_conf, "idmap gid = 10000-39999")

    confset2(smb4_conf, "netbios name = %s", cifs.cifs_srv_netbiosname.upper())
    confset2(smb4_conf, "workgroup = %s", cifs.cifs_srv_workgroup.upper())


def add_activedirectory_conf(smb4_conf):
    try:
        ad = ActiveDirectory.objects.all()[0]
    except:
        return

    cachedir = "/var/tmp/.cache/.samba"

    try:
        os.makedirs(cachedir)
    except:
        pass

    confset2(smb4_conf, "netbios name = %s", ad.ad_netbiosname.upper())
    confset2(smb4_conf, "workgroup = %s", ad.ad_workgroup.upper())
    confset2(smb4_conf, "realm = %s", ad.ad_domainname.upper())
    confset1(smb4_conf, "security = ADS")
    confset1(smb4_conf, "client use spnego = yes")
    confset2(smb4_conf, "cache directory = %s", cachedir)

    confset1(smb4_conf, "local master = no")
    confset1(smb4_conf, "domain master = no")
    confset1(smb4_conf, "preferred master = no")

    confset1(smb4_conf, "acl check permissions = true")
    confset1(smb4_conf, "acl map full control = true")
    confset1(smb4_conf, "dos filemode = yes")

    confset1(smb4_conf, "idmap uid = 10000-19999")
    confset1(smb4_conf, "idmap gid = 10000-19999")

    confset1(smb4_conf, "winbind cache time = 7200")
    confset1(smb4_conf, "winbind offline logon = yes")
    confset1(smb4_conf, "winbind enum users = yes")
    confset1(smb4_conf, "winbind enum groups = yes")
    confset1(smb4_conf, "winbind nested groups = yes")
    confset2(smb4_conf, "winbind use default domain = %s",
        "yes" if ad.ad_use_default_domain else "no")
    confset1(smb4_conf, "winbind refresh tickets = yes")

    confset2(smb4_conf, "allow trusted domains = %s",
        "yes" if ad.ad_allow_trusted_doms else "no")

    confset1(smb4_conf, "template shell = /bin/sh")
    confset2(smb4_conf, "template homedir = %s",
        "/home/%D/%U" if ad.ad_use_default_domain else "/home/%U")

    if not ad.ad_unix_extensions:
        confset2(smb4_conf, "idmap config %s: backend = rid", ad.ad_workgroup)
        confset2(smb4_conf, "idmap config %s: range = 20000-20000000", ad.ad_workgroup)


def add_domaincontroller_conf(smb4_conf):
    try:
        dc = DomainController.objects.all()[0]
        cifs = CIFS.objects.all()[0]
    except:
        return

    #server_services = get_server_services()
    #dcerpc_endpoint_servers = get_dcerpc_endpoint_servers()

    confset2(smb4_conf, "netbios name = %s", cifs.cifs_srv_netbiosname.upper())
    confset2(smb4_conf, "workgroup = %s", dc.dc_domain.upper())
    confset2(smb4_conf, "realm = %s", dc.dc_realm)
    confset2(smb4_conf, "dns forwarder = %s", dc.dc_dns_forwarder)
    confset1(smb4_conf, "idmap_ldb:use rfc2307 = yes")

    #confset2(smb4_conf, "server services = %s",
    #    string.join(server_services, ',').rstrip(','))
    #confset2(smb4_conf, "dcerpc endpoint servers = %s",
    #    string.join(dcerpc_endpoint_servers, ',').rstrip(','))


def generate_smb4_tdb(smb4_tdb):
    try:
        users = bsdUsers.objects.filter(bsdusr_smbhash__regex=r'^.+:.+:XXXX.+$',
            bsdusr_locked=0, bsdusr_password_disabled=0)
        for u in users:
            smb4_tdb.append(u.bsdusr_smbhash)
    except:
        return


def generate_smb4_conf(smb4_conf):
    try:
        cifs = CIFS.objects.all()[0]
    except:
        return

    if not cifs.cifs_srv_guest:
        cifs.cifs_srv_guest = 'ftp'
    if not cifs.cifs_srv_filemask:
        cifs.cifs_srv_filemask = "0666"
    if not cifs.cifs_srv_dirmask:
        cifs.cifs_srv_dirmask = "0777"

    # standard stuff... should probably do this differently
    confset1(smb4_conf, "[global]", space=0)

    confset2(smb4_conf, "server min protocol = %s", cifs.cifs_srv_min_protocol)
    confset2(smb4_conf, "server max protocol = %s", cifs.cifs_srv_max_protocol)

    confset1(smb4_conf, "encrypt passwords = yes")
    confset1(smb4_conf, "dns proxy = no")
    confset1(smb4_conf, "strict locking = no")
    confset1(smb4_conf, "oplocks = yes")
    confset1(smb4_conf, "deadtime = 15")
    confset1(smb4_conf, "max log size = 51200")

    if cifs.cifs_srv_syslog:
        confset1(smb4_conf, "syslog only = yes")
        confset1(smb4_conf, "syslog = 1")

    confset1(smb4_conf, "load printers = no")
    confset1(smb4_conf, "printing = bsd")
    confset1(smb4_conf, "printcap name = /dev/null")
    confset1(smb4_conf, "disable spoolss = yes")
    confset1(smb4_conf, "getwd cache = yes")
    confset2(smb4_conf, "guest account = %s", cifs.cifs_srv_guest.encode('utf8'))
    confset1(smb4_conf, "map to guest = Bad User")
    confset1(smb4_conf, "obey pam restrictions = Yes")
    confset1(smb4_conf, "directory name cache size = 0")

    confset1(smb4_conf, "panic action = /usr/local/libexec/samba/samba-backtrace")

    confset2(smb4_conf, "server string = %s", cifs.cifs_srv_description)
    confset2(smb4_conf, "ea support = %s",
        "yes" if cifs.cifs_srv_easupport else False)
    confset2(smb4_conf, "store dos attributes = %s",
        "yes" if cifs.cifs_srv_dosattr else False)
    if cifs.cifs_srv_dosattr:
        confset1(smb4_conf, "map archive = no")
        confset1(smb4_conf, "map readonly = no")
        confset1(smb4_conf, "map hidden = no")
        confset1(smb4_conf, "map system = no")
    confset2(smb4_conf, "hostname lookups = %s",
        "yes" if cifs.cifs_srv_hostlookup else False)
    confset2(smb4_conf, "unix extensions = %s",
        "no" if not cifs.cifs_srv_unixext else False)
    confset2(smb4_conf, "time server = %s",
        "yes" if cifs.cifs_srv_timeserver else False)
    confset2(smb4_conf, "null passwords = %s",
        "yes" if cifs.cifs_srv_nullpw else False)

    role = get_server_role()
    if cifs.cifs_srv_localmaster and not nt4_enabled() \
        and not activedirectory_enabled():
        confset2(smb4_conf, "local master = %s",
            "yes" if cifs.cifs_srv_localmaster else False)

    if role == 'auto':
        confset1(smb4_conf, "server role = auto")

    elif role == 'classic':
        confset1(smb4_conf, "server role = classic primary domain controller")

    elif role == 'netbios':
        confset1(smb4_conf, "server role = netbios backup domain controller")

    elif role == 'dc':
        confset1(smb4_conf, "server role = active directory domain controller")
        add_domaincontroller_conf(smb4_conf)

    elif role == 'member':
        confset1(smb4_conf, "server role = member server")

        if nt4_enabled():
            add_nt4_conf(smb4_conf)

        elif ldap_enabled():
            add_ldap_conf(smb4_conf)

        elif activedirectory_enabled():
            add_activedirectory_conf(smb4_conf)

    elif role == 'standalone':
        confset1(smb4_conf, "server role = standalone")
        confset2(smb4_conf, "netbios name = %s", cifs.cifs_srv_netbiosname.upper())
        confset2(smb4_conf, "workgroup = %s", cifs.cifs_srv_workgroup.upper())
        confset1(smb4_conf, "security = user")

    if role != 'dc':
        confset1(smb4_conf, "pid directory = /var/run/samba")
        confset1(smb4_conf, "smb passwd file = /var/etc/private/smbpasswd")
        confset1(smb4_conf, "private dir = /var/etc/private")

    confset2(smb4_conf, "create mask = %s", cifs.cifs_srv_filemask)
    confset2(smb4_conf, "directory mask = %s", cifs.cifs_srv_dirmask)
    confset1(smb4_conf, "client ntlmv2 auth = yes")
    confset2(smb4_conf, "dos charset = %s", cifs.cifs_srv_doscharset)
    confset2(smb4_conf, "unix charset = %s", cifs.cifs_srv_unixcharset)

    if cifs.cifs_srv_loglevel and cifs.cifs_srv_loglevel is not True:
        confset2(smb4_conf, "log level = %s", cifs.cifs_srv_loglevel)

    for line in cifs.cifs_srv_smb_options.split('\n'):
        confset1(smb4_conf, line)

    if cifs.cifs_srv_homedir_enable:
        valid_users_path = "%U"
        valid_users = "%U"

        if activedirectory_enabled():
            try:
                ad = ActiveDirectory.objects.all()[0]
                if not ad.ad_use_default_domain:
                    valid_users_path = "%D/%U"
                    valid_users = "%D\%U"
            except:
                pass

        if cifs.cifs_srv_homedir:
            cifs_homedir_path = "%s/%s" % (cifs.cifs_srv_homedir, valid_users_path)
        else:
            cifs_homedir_path = False

        confset1(smb4_conf, "\n")
        confset1(smb4_conf, "[homes]", space=0)
        confset1(smb4_conf, "comment = Home Directories")
        confset2(smb4_conf, "valid users = %s", valid_users)
        confset1(smb4_conf, "writable = yes")
        confset2(smb4_conf, "browseable = %s",
            "yes" if cifs.cifs_srv_homedir_browseable_enable else "no")
        if cifs_homedir_path:
            confset2(smb4_conf, "path = %s", cifs_homedir_path)

        for line in cifs.cifs_srv_homedir_aux.split('\n'):
            confset1(smb4_conf, line)


def generate_smb4_shares(smb4_shares):
    try:
        shares = CIFS_Share.objects.all()
    except:
        return

    if len(shares) == 0:
        return

    p = pipeopen("zfs list -H -o mountpoint,name")
    zfsout = p.communicate()[0].split('\n')
    if p.returncode != 0:
        zfsout = []

    for share in shares:
        if not os.path.isdir(share.cifs_path):
            continue

        task = False
        for line in zfsout:
            try:
                zfs_mp, zfs_ds = line.split()
                if share.cifs_path == zfs_mp or share.cifs_path.startswith("%s/" % zfs_mp):
                    if share.cifs_path == zfs_mp:
                        task = Task.objects.filter(task_filesystem = zfs_ds)[0]
                    else:
                        task = Task.objects.filter(Q(task_filesystem = zfs_ds) & Q(task_recursive=True))[0]
                    break
            except:
                pass

        confset1(smb4_shares, "\n")
        confset2(smb4_shares, "[%s]", share.cifs_name.encode('utf8'), space=0)
        confset2(smb4_shares, "path = %s", share.cifs_path.encode('utf8'))
        confset1(smb4_shares, "printable = no")
        confset1(smb4_shares, "veto files = /.snap/.windows/.zfs/")
        confset2(smb4_shares, "comment = %s", share.cifs_comment.encode('utf8'))
        confset2(smb4_shares, "writeable = %s",
            "no" if share.cifs_ro else "yes")
        confset2(smb4_shares, "browseable = %s",
            "yes" if share.cifs_browsable else "no")

        if notifier().get_dataset_share_type(
            share.cifs_path.replace("/mnt/", "", 1)) != "windows":
            confset2(smb4_shares, "inherit owner = %s",
                "yes" if share.cifs_inheritowner else "no")
            confset2(smb4_shares, "inherit permissions = %s",
                "yes" if share.cifs_inheritperms else "no")

        vfs_objects = []
        if share.cifs_recyclebin:
            vfs_objects.append('recycle')
        if task:
            vfs_objects.append('shadow_copy2')
        if is_within_zfs(share.cifs_path):
            vfs_objects.append('zfsacl')
        vfs_objects.append('streams_xattr')
        vfs_objects.append('aio_pthread')

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
            confset1(smb4_shares, "shadow:format = auto-%%Y%%m%%d.%%H%%M-%s%s" % (
                task.task_ret_count, task.task_ret_unit[0]))
        if vfs_objects:
            confset2(smb4_shares, "vfs objects = %s", ' '.join(vfs_objects).encode('utf8'))

        confset2(smb4_shares, "hide dot files = %s",
            "no" if share.cifs_showhiddenfiles else "yes")
        confset2(smb4_shares, "hosts allow = %s", share.cifs_hostsallow)
        confset2(smb4_shares, "hosts deny = %s", share.cifs_hostsdeny)
        confset2(smb4_shares, "guest ok = %s", "yes" if share.cifs_guestok else "no")

        confset2(smb4_shares, "guest only = %s",
            "yes" if share.cifs_guestonly else False)

        confset2(smb4_shares, "inherit acls = %s",
            "yes" if share.cifs_inheritacls else "no")

        confset1(smb4_shares, "nfs4:mode = special")
        confset1(smb4_shares, "nfs4:acedup = merge")
        confset1(smb4_shares, "nfs4:chown = yes")
        confset1(smb4_shares, "zfsacl:acesort = dontcare")

        for line in share.cifs_auxsmbconf.split('\n'):
            confset1(smb4_shares, line)


def provision_smb4():
    if not Samba4().domain_provision():
        print >> sys.stderr, "Failed to provision domain"
        return False

    if not Samba4().disable_password_complexity():
        print >> sys.stderr, "Failed to disable password complexity"
        return False

    if not Samba4().set_administrator_password():
        print >> sys.stderr, "Failed to set administrator password"
        return False

    if not Samba4().sentinel_file_create():
        return False

    return True


def smb4_mkdir(dir):
    try:
        os.makedirs(dir)
    except:
        pass


def smb4_unlink(dir):
    try:
        os.unlink(dir)
    except:
        pass


def smb4_setup():
    statedir = "/var/db/samba4"

    smb4_mkdir("/var/run/samba")
    smb4_mkdir("/var/db/samba")

    smb4_mkdir("/var/run/samba4")

    smb4_mkdir("/var/log/samba4")
    os.chmod("/var/log/samba4", 0755)

    smb4_mkdir("/var/etc/private")
    os.chmod("/var/etc/private", 0700)

    smb4_unlink("/usr/local/etc/smb.conf")
    smb4_unlink("/usr/local/etc/smb4.conf")

    if hasattr(notifier, 'failover_status') and notifier().failover_status() == 'BACKUP':
        return

    volume, basename = get_samba4_path()
    basename_realpath = "/mnt/%s" % basename
    statedir_realpath = os.path.realpath(statedir)

    if not volume.is_decrypted():
        if (basename_realpath == statedir_realpath and os.path.islink(statedir)) or \
            os.path.islink(statedir):
            smb4_unlink(statedir)  
            smb4_mkdir(statedir)
        return

    if basename_realpath != statedir_realpath and os.path.exists(basename_realpath):
        smb4_unlink(statedir)  
        if os.path.exists(statedir):
            olddir = "%s.%s" % (statedir, time.strftime("%Y%m%d%H%M%S"))
            try:
                os.rename(statedir, olddir)
            except Exception as e:
                print >> sys.stderr, "Unable to rename '%s' to '%s' (%s)" % (
                    statedir, olddir, e)
                sys.exit(1)  

        try:
            os.symlink(basename_realpath, statedir)
        except Exception as e:
            print >> sys.stderr, "Unable to create symlink '%s' -> '%s' (%s)" % (
                basename_realpath, statedir, e)
            sys.exit(1)  

    if os.path.islink(statedir) and not os.path.exists(statedir_realpath):
        smb4_unlink(statedir)  
        smb4_mkdir(statedir)


def get_old_samba4_datasets():
    old_samba4_datasets = []

    fsvols = notifier().list_zfs_fsvols()
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


def do_migration(old_samba4_datasets):
    if len(old_samba4_datasets) > 1:
        return False
    old_samba4_dataset = "/mnt/%s/" % old_samba4_datasets[0]

    try:
        pipeopen("/usr/local/bin/rsync -avz '%s'* '/var/db/samba4/'" % old_samba4_dataset).wait()
        notifier().destroy_zfs_dataset(old_samba4_datasets[0], True)

    except Exception as e:
        print >> sys.stderr, e
    
    return True


def main():
    smb_conf_path = "/usr/local/etc/smb4.conf"

    smb4_tdb = []
    smb4_conf = []
    smb4_shares = []

    smb4_setup()

    old_samba4_datasets = get_old_samba4_datasets()
    if migration_available(old_samba4_datasets):
        do_migration(old_samba4_datasets)

    generate_smb4_tdb(smb4_tdb)
    generate_smb4_conf(smb4_conf)
    generate_smb4_shares(smb4_shares)

    role = get_server_role()
    if role == 'dc' and not Samba4().domain_provisioned():
        provision_smb4()

    with open(smb_conf_path, "w") as f:
        for line in smb4_conf:
            f.write(line + '\n')
        for line in smb4_shares:
            f.write(line + '\n')
        f.close()

    (fd, tmpfile) = tempfile.mkstemp(dir="/tmp")
    for line in smb4_tdb:
        os.write(fd, line + '\n')
    os.close(fd)

    if role != 'dc':
        p = pipeopen("/usr/local/bin/pdbedit -d 0 -i smbpasswd:%s -e %s -s %s" % (
            tmpfile, "tdbsam:/var/etc/private/passdb.tdb", smb_conf_path))
        out = p.communicate()
        if out and out[1]:
            for line in out[1].split('\n'):
                print line
        os.unlink(tmpfile)


if __name__ == '__main__':
    main()
