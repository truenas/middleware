#!/usr/local/bin/python2
from collections import defaultdict

import os
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()


from freenasUI.middleware import zfs

# NOTE
# Normally global variables are a bad idea, and this is no
# exception, however it was the best choice given that the
# alternatives were duplicating a lot of code or doing
# even more modifications to this script. Ideally you'd
# instantiate a config object (or two)...

# This file has plain text CHAP users and passwords in it, and is
# the config file used by CTL.
ctl_config = "/etc/ctl.conf"
cf_contents = []
# This file has the CHAP usernames and passwords replaced with
# REDACTED.  It is consumed by freenas-debug.  We generate both
# files every time the system determines a new config file
# needs to be created from the database.
ctl_config_shadow = "/etc/ctl.conf.shadow"
cf_contents_shadow = []


def addline(line, plaintextonly=False, shadowonly=False):
    # Add "line" to both the shadow and plaintext config files
    # The plaintextonly and shadowonly switches allow adding
    # to only one of the files.  This is used in the one place
    # that the shadow file diverges from the plain text file:
    # CHAP passwords
    if plaintextonly == shadowonly:
        cf_contents.append(line)
        cf_contents_shadow.append(line)
    elif plaintextonly:
        cf_contents.append(line)
    elif shadowonly:
        cf_contents_shadow.append(line)


def auth_group_config(auth_tag=None, auth_list=None, auth_type=None, initiator=None):
    addline("auth-group ag%s {\n" % auth_tag)
    # It is an error to mix CHAP and Mutual CHAP in the same auth group
    # But not in istgt, so we need to catch this and do something.
    # For now just skip over doing something that would cause ctld to bomb
    rv = False
    if auth_list is None:
        auth_list = []
    for auth in auth_list:
        if auth.iscsi_target_auth_peeruser and auth_type != "CHAP":
            rv = True
            auth_type = "Mutual"
            addline("\tchap-mutual %s \"%s\" %s \"%s\"\n" % (
                auth.iscsi_target_auth_user,
                auth.iscsi_target_auth_secret,
                auth.iscsi_target_auth_peeruser,
                auth.iscsi_target_auth_peersecret,
            ), plaintextonly=True)
            addline("\tchap-mutual REDACTED REDACTED REDACTED REDACTED\n", shadowonly=True)
        elif auth_type != "Mutual":
            rv = True
            auth_type = "CHAP"
            addline("\tchap %s \"%s\"\n" % (
                auth.iscsi_target_auth_user,
                auth.iscsi_target_auth_secret,
            ), plaintextonly=True)
            addline("\tchap REDACTED REDACTED\n", shadowonly=True)

    if initiator:
        if initiator.iscsi_target_initiator_initiators:
            sep = "\n"
            if "," in initiator.iscsi_target_initiator_initiators:
                sep = ","
            elif " " in initiator.iscsi_target_initiator_initiators:
                sep = " "
            for name in initiator.iscsi_target_initiator_initiators.strip('\n').split(sep):
                if name == 'ALL':
                    continue
                rv = True
                addline("""\tinitiator-name "%s"\n""" % name.lstrip())
        if initiator.iscsi_target_initiator_auth_network:
            sep = "\n"
            if "," in initiator.iscsi_target_initiator_auth_network:
                sep = ","
            elif " " in initiator.iscsi_target_initiator_auth_network:
                sep = " "
            for name in initiator.iscsi_target_initiator_auth_network.strip('\n').split(sep):
                if name == 'ALL':
                    continue
                rv = True
                addline("""\tinitiator-portal "%s"\n""" % name.lstrip())
        if rv and not auth_list and auth_type == 'None':
            addline("\tauth-type \"none\"\n")
    addline("}\n\n")
    return rv


def main():
    """Use the django ORM to generate a config file.  We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    from freenasUI.services.models import iSCSITargetGlobalConfiguration
    from freenasUI.services.models import iSCSITargetPortal
    from freenasUI.services.models import iSCSITargetPortalIP
    from freenasUI.services.models import iSCSITargetAuthCredential
    from freenasUI.services.models import iSCSITarget
    from freenasUI.storage.models import Disk

    gconf = iSCSITargetGlobalConfiguration.objects.order_by('-id')[0]

    if gconf.iscsi_isns_servers:
        for server in gconf.iscsi_isns_servers.split(' '):
            addline('isns-server %s\n\n' % server)

    # We support multiple authentications for a single group
    auths = defaultdict(list)
    for auth in iSCSITargetAuthCredential.objects.order_by('iscsi_target_auth_tag'):
        auths[auth.iscsi_target_auth_tag].append(auth)

    for auth_tag, auth_list in auths.items():
        auth_group_config(auth_tag, auth_list)

    # Generate the portal-group section
    for portal in iSCSITargetPortal.objects.all():
        addline("portal-group pg%s {\n" % portal.iscsi_target_portal_tag)
        addline("\tdiscovery-filter portal-name\n")
        disc_authmethod = portal.iscsi_target_portal_discoveryauthmethod
        if disc_authmethod == "None" or ((disc_authmethod == "Auto" or disc_authmethod == "auto") and portal.iscsi_target_portal_discoveryauthgroup is None):
            addline("\tdiscovery-auth-group no-authentication\n")
        else:
            addline("\tdiscovery-auth-group ag%s\n" % portal.iscsi_target_portal_discoveryauthgroup)
        listen = iSCSITargetPortalIP.objects.filter(iscsi_target_portalip_portal=portal)
        for obj in listen:
            if ':' in obj.iscsi_target_portalip_ip:
                address = '[%s]' % obj.iscsi_target_portalip_ip
            else:
                address = obj.iscsi_target_portalip_ip
            addline("\tlisten %s:%s\n" % (address, obj.iscsi_target_portalip_port))
        addline("}\n\n")

    # Cache zpool threshold
    poolthreshold = {}
    zpoollist = zfs.zpool_list()

    # Generate the target section
    target_basename = gconf.iscsi_basename
    for target in iSCSITarget.objects.all():
        if target.iscsi_target_authgroup:
            auth_list = iSCSITargetAuthCredential.objects.filter(iscsi_target_auth_tag=target.iscsi_target_authgroup)
        else:
            auth_list = []
        agname = '4tg_%d' % target.id
        has_auth = auth_group_config(auth_tag=agname, auth_list=auth_list, auth_type=target.iscsi_target_authtype, initiator=target.iscsi_target_initiatorgroup)
        if (target.iscsi_target_name.startswith("iqn.") or
                target.iscsi_target_name.startswith("eui.") or
                target.iscsi_target_name.startswith("naa.")):
            addline("target %s {\n" % target.iscsi_target_name)
        else:
            addline("target %s:%s {\n" % (target_basename, target.iscsi_target_name))
        if target.iscsi_target_alias:
            addline("\talias \"%s\"\n" % target.iscsi_target_alias)
        elif target.iscsi_target_name:
            addline("\talias \"%s\"\n" % target.iscsi_target_name)
        if not has_auth:
            addline("\tauth-group no-authentication\n")
        else:
            addline("\tauth-group ag%s\n" % agname)
        addline("\tportal-group pg%d\n" % (
            target.iscsi_target_portalgroup.iscsi_target_portal_tag,
        ))
        used_lunids = [
            o.iscsi_lunid
            for o in target.iscsitargettoextent_set.all().exclude(
                iscsi_lunid=None,
            )
        ]
        cur_lunid = 0
        for t2e in target.iscsitargettoextent_set.all().extra({
            'null_first': 'iscsi_lunid IS NULL',
        }).order_by('null_first', 'iscsi_lunid'):

            path = t2e.iscsi_extent.iscsi_target_extent_path
            unmap = False
            poolname = None
            lunthreshold = None
            if t2e.iscsi_extent.iscsi_target_extent_type == 'Disk':
                disk = Disk.objects.filter(id=path).order_by('disk_enabled')
                if not disk.exists():
                    continue
                disk = disk[0]
                if disk.disk_multipath_name:
                    path = "/dev/multipath/%s" % disk.disk_multipath_name
                else:
                    path = "/dev/%s" % disk.identifier_to_device()
            else:
                if not path.startswith("/mnt"):
                    poolname = path.split('/', 2)[1]
                    if gconf.iscsi_pool_avail_threshold:
                        if poolname in zpoollist:
                            poolthreshold[poolname] = int(
                                zpoollist.get(poolname).get('size') * (
                                    gconf.iscsi_pool_avail_threshold / 100.0
                                )
                            )
                    if t2e.iscsi_extent.iscsi_target_extent_avail_threshold:
                        zvolname = path.split('/', 1)[1]
                        zfslist = zfs.zfs_list(path=zvolname, types=['volume'])
                        if zfslist:
                            lunthreshold = int(zfslist[zvolname].volsize * (t2e.iscsi_extent.iscsi_target_extent_avail_threshold / 100.0))
                    path = "/dev/" + path
                    unmap = True
                else:
                    if t2e.iscsi_extent.iscsi_target_extent_avail_threshold and os.path.exists(path):
                        try:
                            stat = os.stat(path)
                            lunthreshold = int(stat.st_size * (t2e.iscsi_extent.iscsi_target_extent_avail_threshold / 100.0))
                        except OSError:
                            pass
            if os.path.exists(path):
                addline("\t\t\n")
                if t2e.iscsi_lunid is None:
                    while cur_lunid in used_lunids:
                        cur_lunid += 1
                    addline("\t\tlun %s {\n" % cur_lunid)
                    cur_lunid += 1
                else:
                    addline("\t\tlun %s {\n" % t2e.iscsi_lunid)
                size = t2e.iscsi_extent.iscsi_target_extent_filesize
                if unmap:
                    addline("\t\t\toption unmap on\n")
                addline("\t\t\tpath %s\n" % path)
                addline("\t\t\tblocksize %s\n" % t2e.iscsi_extent.iscsi_target_extent_blocksize)
                if t2e.iscsi_extent.iscsi_target_extent_pblocksize:
                    addline("\t\t\toption pblocksize 0\n")
                if t2e.iscsi_lunid is None:
                    addline("\t\t\tserial %s%s\n" % (target.iscsi_target_serial, str(cur_lunid-1)))
                else:
                    addline("\t\t\tserial %s%s\n" % (target.iscsi_target_serial, str(t2e.iscsi_lunid)))
                padded_serial = target.iscsi_target_serial
                if t2e.iscsi_lunid is None:
                    padded_serial += str(cur_lunid-1)
                else:
                    padded_serial += str(t2e.iscsi_lunid)
                if not t2e.iscsi_extent.iscsi_target_extent_xen:
                    for i in xrange(31-len(target.iscsi_target_serial)):
                        padded_serial += " "
                addline('\t\t\tdevice-id "iSCSI Disk      %s"\n' % padded_serial)
                if size != "0":
                    if size.endswith('B'):
                        size = size.strip('B')
                    addline("\t\t\tsize %s\n" % size)
                addline('\t\t\toption vendor "FreeBSD"\n')
                addline('\t\t\toption product "iSCSI Disk"\n')
                addline('\t\t\toption revision "0123"\n')
                addline('\t\t\toption naa %s\n' % t2e.iscsi_extent.iscsi_target_extent_naa)
                if t2e.iscsi_extent.iscsi_target_extent_insecure_tpc:
                    addline('\t\t\toption insecure_tpc on\n')

                if lunthreshold:
                    addline('\t\t\toption avail-threshold %s\n' % lunthreshold)
                if poolname is not None and poolname in poolthreshold:
                    addline('\t\t\toption pool-avail-threshold %s\n' % poolthreshold[poolname])
                if t2e.iscsi_extent.iscsi_target_extent_rpm == "Unknown":
                    addline('\t\t\toption rpm 0\n')
                elif t2e.iscsi_extent.iscsi_target_extent_rpm == "SSD":
                    addline('\t\t\toption rpm 1\n')
                else:
                    addline('\t\t\toption rpm %s\n' % t2e.iscsi_extent.iscsi_target_extent_rpm)
                addline("\t\t}\n")
        addline("}\n\n")

    os.umask(077)
    # Write out the CTL config file
    fh = open(ctl_config, "w")
    for line in cf_contents:
        fh.write(line)
    fh.close()

    # Write out the CTL config file with redacted CHAP passwords
    fh = open(ctl_config_shadow, "w")
    for line in cf_contents_shadow:
        fh.write(line)
    fh.close()

if __name__ == "__main__":
    main()
