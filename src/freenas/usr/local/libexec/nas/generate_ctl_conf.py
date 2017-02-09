#!/usr/local/bin/python2
from middlewared.client import Client
from middlewared.client.utils import Struct
import logging
import logging.config
import os

log = logging.getLogger('clt.conf.py')

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
    # First prepare all the lists, filtering out garpage.
    if auth_list is None:
        auth_list = []
    inames = []
    inets = []
    if initiator:
        if initiator.iscsi_target_initiator_initiators:
            sep = "\n"
            if "," in initiator.iscsi_target_initiator_initiators:
                sep = ","
            elif " " in initiator.iscsi_target_initiator_initiators:
                sep = " "
            inames = initiator.iscsi_target_initiator_initiators.strip('\n').split(sep)
            inames = [x for x in inames if x != 'ALL' and x != '']
        if initiator.iscsi_target_initiator_auth_network:
            sep = "\n"
            if "," in initiator.iscsi_target_initiator_auth_network:
                sep = ","
            elif " " in initiator.iscsi_target_initiator_auth_network:
                sep = " "
            inets = initiator.iscsi_target_initiator_auth_network.strip('\n').split(sep)
            inets = [x for x in inets if x != 'ALL' and x != '']

    # If nothing left after filtering, then we are done.
    if not inames and not inets and not auth_list and (auth_type == 'None' or auth_type == 'auto'):
        return False

    # There are some real paremeters, so write the auth group.
    addline("auth-group ag%s {\n" % auth_tag)
    for name in inames:
        addline("""\tinitiator-name "%s"\n""" % name.lstrip())
    for name in inets:
        addline("""\tinitiator-portal "%s"\n""" % name.lstrip())
    # It is an error to mix CHAP and Mutual CHAP in the same auth group
    # But not in istgt, so we need to catch this and do something.
    # For now just skip over doing something that would cause ctld to bomb
    for auth in auth_list:
        if auth.iscsi_target_auth_peeruser and auth_type != "CHAP":
            auth_type = "Mutual"
            addline("\tchap-mutual %s \"%s\" %s \"%s\"\n" % (
                auth.iscsi_target_auth_user,
                auth.iscsi_target_auth_secret,
                auth.iscsi_target_auth_peeruser,
                auth.iscsi_target_auth_peersecret,
            ), plaintextonly=True)
            addline("\tchap-mutual REDACTED REDACTED REDACTED REDACTED\n", shadowonly=True)
        elif auth_type != "Mutual":
            auth_type = "CHAP"
            addline("\tchap %s \"%s\"\n" % (
                auth.iscsi_target_auth_user,
                auth.iscsi_target_auth_secret,
            ), plaintextonly=True)
            addline("\tchap REDACTED REDACTED\n", shadowonly=True)
    if not auth_list and (auth_type == 'None' or auth_type == 'auto'):
        addline("\tauth-type \"none\"\n")
    addline("}\n\n")
    return True


def main():
    """Use the middleware client to generate a config file. We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    client = Client()

    gconf = Struct(client.call('datastore.query', 'services.iSCSITargetGlobalConfiguration', None, {'get': True}))

    if gconf.iscsi_isns_servers:
        for server in gconf.iscsi_isns_servers.split(' '):
            addline('isns-server %s\n\n' % server)

    # Generate the portal-group section
    addline('portal-group default {\n}\n\n')
    for portal in client.call('datastore.query', 'services.iSCSITargetPortal'):
        portal = Struct(portal)
        # Prepare auth group for the portal group
        if portal.iscsi_target_portal_discoveryauthgroup:
            auth_list = [
                Struct(i)
                for i in client.call('datastore.query', 'services.iSCSITargetAuthCredential', [('iscsi_target_auth_tag', '=', portal.iscsi_target_portal_discoveryauthgroup)])
            ]
        else:
            auth_list = []
        agname = '4pg%d' % portal.iscsi_target_portal_tag
        auth = auth_group_config(auth_tag=agname,
                                 auth_list=auth_list,
                                 auth_type=portal.iscsi_target_portal_discoveryauthmethod)

        addline("portal-group pg%s {\n" % portal.iscsi_target_portal_tag)
        addline("\tdiscovery-filter portal-name\n")
        if auth:
            addline("\tdiscovery-auth-group ag%s\n" % agname)
        else:
            addline("\tdiscovery-auth-group no-authentication\n")
        listen = [
            Struct(i)
            for i in client.call('datastore.query', 'services.iSCSITargetPortalIP', [('iscsi_target_portalip_portal', '=', portal.id)])
        ]
        for obj in listen:
            if ':' in obj.iscsi_target_portalip_ip:
                address = '[%s]' % obj.iscsi_target_portalip_ip
            else:
                address = obj.iscsi_target_portalip_ip
            addline("\tlisten %s:%s\n" % (address, obj.iscsi_target_portalip_port))
        addline("\toption ha_shared on\n")
        addline("}\n\n")

    # Cache zpool threshold
    poolthreshold = {}
    zpoollist = client.call('notifier.zpool_list')

    # Generate the LUN section
    for extent in client.call('datastore.query', 'services.iSCSITargetExtent'):
        extent = Struct(extent)
        path = extent.iscsi_target_extent_path
        if not path:
            log.warn('Path for extent id %d is null, skipping', extent.id)
            continue

        poolname = None
        lunthreshold = None
        if extent.iscsi_target_extent_type == 'Disk':
            disk = client.call('datastore.query', 'storage.Disk', [('disk_identifier', '=', path)], {'order_by': ['disk_enabled']})
            if not disk:
                continue
            disk = Struct(disk[0])
            if disk.disk_multipath_name:
                path = "/dev/multipath/%s" % disk.disk_multipath_name
            else:
                path = "/dev/%s" % client.call('notifier.identifier_to_device', disk.disk_identifier)
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
                if extent.iscsi_target_extent_avail_threshold:
                    zvolname = path.split('/', 1)[1]
                    zfslist = client.call('notifier.zfs_list', zvolname, False, False, False, ['volume'])
                    if zfslist:
                        lunthreshold = int(zfslist[zvolname]['volsize'] *
                                           (extent.iscsi_target_extent_avail_threshold / 100.0))
                path = "/dev/" + path
            else:
                if extent.iscsi_target_extent_avail_threshold and os.path.exists(path):
                    try:
                        stat = os.stat(path)
                        lunthreshold = int(stat.st_size *
                                           (extent.iscsi_target_extent_avail_threshold / 100.0))
                    except OSError:
                        pass
        addline("lun \"%s\" {\n" % extent.iscsi_target_extent_name)
        size = extent.iscsi_target_extent_filesize
        addline("\tpath \"%s\"\n" % path)
        addline("\tblocksize %s\n" % extent.iscsi_target_extent_blocksize)
        if extent.iscsi_target_extent_pblocksize:
            addline("\toption pblocksize 0\n")
        addline("\tserial \"%s\"\n" % (extent.iscsi_target_extent_serial, ))
        padded_serial = extent.iscsi_target_extent_serial
        if not extent.iscsi_target_extent_xen:
            for i in range(31 - len(extent.iscsi_target_extent_serial)):
                padded_serial += " "
        addline('\tdevice-id "iSCSI Disk      %s"\n' % padded_serial)
        if size != "0":
            if size.endswith('B'):
                size = size.strip('B')
            addline("\t\tsize %s\n" % size)

        # We can't change the vendor name of existing
        # LUNs without angering VMWare, but we can
        # use the right names going forward.
        if extent.iscsi_target_extent_legacy is True:
            addline('\toption vendor "FreeBSD"\n')
        else:
            if client.call('notifier.is_freenas'):
                addline('\toption vendor "FreeNAS"\n')
            else:
                addline('\toption vendor "TrueNAS"\n')

        addline('\toption product "iSCSI Disk"\n')
        addline('\toption revision "0123"\n')
        addline('\toption naa %s\n' % extent.iscsi_target_extent_naa)
        if extent.iscsi_target_extent_insecure_tpc:
            addline('\toption insecure_tpc on\n')
            if lunthreshold:
                addline('\toption avail-threshold %s\n' % lunthreshold)
        if poolname is not None and poolname in poolthreshold:
            addline('\toption pool-avail-threshold %s\n' % poolthreshold[poolname])
        if extent.iscsi_target_extent_rpm == "Unknown":
            addline('\toption rpm 0\n')
        elif extent.iscsi_target_extent_rpm == "SSD":
            addline('\toption rpm 1\n')
        else:
            addline('\toption rpm %s\n' % extent.iscsi_target_extent_rpm)
        if extent.iscsi_target_extent_ro:
            addline('\toption readonly on\n')
        addline("}\n")
        addline("\n")

    # Generate the target section
    target_basename = gconf.iscsi_basename
    for target in client.call('datastore.query', 'services.iSCSITarget'):
        target = Struct(target)

        authgroups = {}
        for grp in client.call('datastore.query', 'services.iscsitargetgroups', [('iscsi_target', '=', target.id)]):
            grp = Struct(grp)
            if grp.iscsi_target_authgroup:
                auth_list = [
                    Struct(i)
                    for i in client.call('datastore.query', 'services.iSCSITargetAuthCredential', [('iscsi_target_auth_tag', '=', grp.iscsi_target_authgroup)])
                ]
            else:
                auth_list = []
            agname = '4tg%d_%d' % (target.id, grp.id)
            if auth_group_config(auth_tag=agname,
                                 auth_list=auth_list,
                                 auth_type=grp.iscsi_target_authtype,
                                 initiator=grp.iscsi_target_initiatorgroup):
                authgroups[grp.id] = agname
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

        for fctt in client.call('datastore.query', 'services.fibrechanneltotarget', [('fc_target', '=', target.id)]):
            fctt = Struct(fctt)
            addline("\tport %s\n" % fctt.fc_port)

        for grp in client.call('datastore.query', 'services.iscsitargetgroups', [('iscsi_target', '=', target.id)]):
            grp = Struct(grp)
            agname = authgroups.get(grp.id) or None
            addline("\tportal-group pg%d %s\n" % (
                grp.iscsi_target_portalgroup.iscsi_target_portal_tag,
                'ag' + agname if agname else 'no-authentication',
            ))
        addline("\n")
        used_lunids = [
            o['iscsi_lunid']
            for o in client.call('datastore.query', 'services.iscsitargettoextent', [('iscsi_target', '=', target.id), ('iscsi_lunid', '!=', None)])
        ]
        cur_lunid = 0
        for t2e in client.call('datastore.query', 'services.iscsitargettoextent', [('iscsi_target', '=', target.id)], {'extra': {'select': {'null_first': 'iscsi_lunid IS NULL'}}, 'order_by': ['null_first', 'iscsi_lunid']}):
            t2e = Struct(t2e)

            if t2e.iscsi_lunid is None:
                while cur_lunid in used_lunids:
                    cur_lunid += 1
                addline("\tlun %s \"%s\"\n" % (cur_lunid,
                                               t2e.iscsi_extent.iscsi_target_extent_name))
                cur_lunid += 1
            else:
                addline("\tlun %s \"%s\"\n" % (t2e.iscsi_lunid,
                                               t2e.iscsi_extent.iscsi_target_extent_name))
        addline("}\n\n")

    os.umask(0o77)
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
