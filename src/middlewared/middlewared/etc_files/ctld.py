from middlewared.client.utils import Struct
import contextlib
import logging
import os
import subprocess
import sysctl

logger = logging.getLogger(__name__)


# NOTE
# Normally global variables are a bad idea, and this is no
# exception, however it was the best choice given that the
# alternatives were duplicating a lot of code or doing
# even more modifications to this script. Ideally you'd
# instantiate a config object (or two)...

# This file has plain text CHAP users and passwords in it, and is
# the config file used by CTL.
ctl_config = '/etc/ctl.conf'
cf_contents = []
# This file has the CHAP usernames and passwords replaced with
# REDACTED.  It is consumed by freenas-debug.  We generate both
# files every time the system determines a new config file
# needs to be created from the database.
ctl_config_shadow = '/etc/ctl.conf.shadow'
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
            sep = '\n'
            if ',' in initiator.iscsi_target_initiator_initiators:
                sep = ','
            elif ' ' in initiator.iscsi_target_initiator_initiators:
                sep = ' '
            inames = initiator.iscsi_target_initiator_initiators.strip('\n').split(sep)
            inames = [x for x in inames if x != 'ALL' and x != '']
        if initiator.iscsi_target_initiator_auth_network:
            sep = '\n'
            if ',' in initiator.iscsi_target_initiator_auth_network:
                sep = ','
            elif ' ' in initiator.iscsi_target_initiator_auth_network:
                sep = ' '
            inets = initiator.iscsi_target_initiator_auth_network.strip('\n').split(sep)
            inets = [x for x in inets if x != 'ALL' and x != '']

    # If nothing left after filtering, then we are done.
    if not inames and not inets and not auth_list and (auth_type == 'None' or auth_type == 'auto'):
        return False

    # There are some real paremeters, so write the auth group.
    addline('auth-group "%s" {\n' % auth_tag)
    for name in inames:
        addline('\tinitiator-name "%s"\n' % name.lstrip())
    for name in inets:
        addline('\tinitiator-portal "%s"\n' % name.lstrip())
    # It is an error to mix CHAP and Mutual CHAP in the same auth group
    # But not in istgt, so we need to catch this and do something.
    # For now just skip over doing something that would cause ctld to bomb
    for auth in auth_list:
        if auth.iscsi_target_auth_peeruser and auth_type != 'CHAP':
            auth_type = 'Mutual'
            addline('\tchap-mutual "%s" "%s" "%s" "%s"\n' % (
                auth.iscsi_target_auth_user,
                auth.iscsi_target_auth_secret,
                auth.iscsi_target_auth_peeruser,
                auth.iscsi_target_auth_peersecret,
            ), plaintextonly=True)
            addline('\tchap-mutual "REDACTED" "REDACTED" "REDACTED" "REDACTED"\n', shadowonly=True)
        elif auth_type != 'Mutual':
            auth_type = 'CHAP'
            addline('\tchap "%s" "%s"\n' % (
                auth.iscsi_target_auth_user,
                auth.iscsi_target_auth_secret,
            ), plaintextonly=True)
            addline('\tchap "REDACTED" "REDACTED"\n', shadowonly=True)
    if not auth_list and (auth_type == 'None' or auth_type == 'auto'):
        addline('\tauth-type "none"\n')
    addline('}\n\n')
    return True


def main(middleware):
    """Use the middleware to generate a config file. We'll build the
    config file as a series of lines, and once that is done write it
    out in one go"""

    cf_contents.clear()
    cf_contents_shadow.clear()

    gconf = Struct(middleware.call_sync('datastore.query', 'services.iSCSITargetGlobalConfiguration',
                                        [], {'get': True}))
    if gconf.iscsi_alua:
        node = middleware.call_sync('failover.node')

    if gconf.iscsi_isns_servers:
        for server in gconf.iscsi_isns_servers.split():
            addline('isns-server "%s"\n\n' % server)

    # Generate the portal-group section
    addline('portal-group "default" {\n}\n\n')
    for pg in middleware.call_sync('datastore.query', 'services.iSCSITargetPortal'):
        pg = Struct(pg)
        # Prepare auth group for the portal group
        if pg.iscsi_target_portal_discoveryauthgroup:
            auth_list = [
                Struct(i)
                for i in middleware.call_sync('datastore.query', 'services.iSCSITargetAuthCredential',
                                              [('iscsi_target_auth_tag', '=',
                                                pg.iscsi_target_portal_discoveryauthgroup)])
            ]
        else:
            auth_list = []
        agname = 'ag4pg%d' % pg.iscsi_target_portal_tag
        if not auth_group_config(auth_tag=agname,
                                 auth_list=auth_list,
                                 auth_type=pg.iscsi_target_portal_discoveryauthmethod):
            agname = 'no-authentication'

        # Prepare IPs to listen on for all portal groups.
        portals = [
            Struct(i)
            for i in middleware.call_sync('datastore.query', 'services.iSCSITargetPortalIP',
                                          [('iscsi_target_portalip_portal', '=', pg.id)])
        ]
        listen = []
        listenA = []
        listenB = []
        for portal in portals:
            if ':' in portal.iscsi_target_portalip_ip:
                address = '[%s]' % portal.iscsi_target_portalip_ip
            else:
                address = portal.iscsi_target_portalip_ip
            found = False
            if gconf.iscsi_alua:
                if address == '0.0.0.0':
                    listenA.append('%s:%s' % (address, portal.iscsi_target_portalip_port))
                    listenB.append('%s:%s' % (address, portal.iscsi_target_portalip_port))
                    found = True
                    break
                if not found:
                    for net in middleware.call_sync('datastore.query', 'network.Interfaces'):
                        if net['int_vip'] == address and net['int_ipv4address'] and net['int_ipv4address_b']:
                            listenA.append('%s:%s' % (net['int_ipv4address'], portal.iscsi_target_portalip_port))
                            listenB.append('%s:%s' % (net['int_ipv4address_b'], portal.iscsi_target_portalip_port))
                            found = True
                            break
                if not found:
                    for alias in middleware.call_sync('datastore.query', 'network.Alias'):
                        if alias['alias_vip'] == address and alias['alias_v4address'] and alias['alias_v4address_b']:
                            listenA.append('%s:%s' % (alias['alias_v4address'], portal.iscsi_target_portalip_port))
                            listenB.append('%s:%s' % (alias['alias_v4address_b'], portal.iscsi_target_portalip_port))
                            found = True
                            break
            else:
                listen.append('%s:%s' % (address, portal.iscsi_target_portalip_port))

        if gconf.iscsi_alua:
            # Two portal groups for ALUA HA case.
            addline('portal-group "pg%dA" {\n' % pg.iscsi_target_portal_tag)
            addline('\ttag "0x%04x"\n' % pg.iscsi_target_portal_tag)
            addline('\tdiscovery-filter "portal-name"\n')
            addline('\tdiscovery-auth-group "%s"\n' % agname)
            for i in listenA:
                addline('\tlisten "%s"\n' % i)
            if node != 'A':
                addline('\tforeign\n')
            addline('}\n')
            addline('portal-group "pg%dB" {\n' % pg.iscsi_target_portal_tag)
            addline('\ttag "0x%04x"\n' % (pg.iscsi_target_portal_tag + 0x8000))
            addline('\tdiscovery-filter "portal-name"\n')
            addline('\tdiscovery-auth-group "%s"\n' % agname)
            for i in listenB:
                addline('\tlisten "%s"\n' % i)
            if node != 'B':
                addline('\tforeign\n')
            addline('}\n\n')
        else:
            # One portal group for non-HA and CARP HA cases.
            addline('portal-group "pg%d" {\n' % pg.iscsi_target_portal_tag)
            addline('\ttag "0x%04x"\n' % pg.iscsi_target_portal_tag)
            addline('\tdiscovery-filter "portal-name"\n')
            addline('\tdiscovery-auth-group "%s"\n' % agname)
            for i in listen:
                addline('\tlisten "%s"\n' % i)
            addline('\toption "ha_shared" "on"\n')
            addline('}\n\n')

    # Cache zpool threshold
    poolthreshold = {}
    zpoollist = {i['name']: i for i in middleware.call_sync('zfs.pool.query')}

    system_disks = middleware.call_sync('device.get_disks')
    extents = {}
    locked_extents = {}
    for extent in middleware.call_sync('iscsi.extent.query'):
        extents[extent['id']] = extent
        if extent['locked']:
            locked_extents[extent['id']] = extent
    # Generate the LUN section
    for extent in middleware.call_sync('datastore.query', 'services.iSCSITargetExtent',
                                       [['iscsi_target_extent_enabled', '=', True]]):
        extent = Struct(extent)
        if extent.id in locked_extents:
            logger.warning('Extent %r is locked, skipping', extent.iscsi_target_extent_name)
            middleware.call_sync('iscsi.extent.generate_locked_alert', extent.id)
            continue

        path = extent.iscsi_target_extent_path
        if not path:
            logger.warning('Path for extent id %d is null, skipping', extent.id)
            continue

        poolname = None
        lunthreshold = None
        if extent.iscsi_target_extent_type == 'Disk':
            disk = middleware.call_sync('datastore.query', 'storage.Disk',
                                        [('disk_identifier', '=', path)],
                                        {'order_by': ['disk_expiretime']})
            if not disk:
                continue
            disk = Struct(disk[0])
            if disk.disk_multipath_name:
                path = '/dev/multipath/%s' % disk.disk_multipath_name
            else:
                path = '/dev/%s' % middleware.call_sync(
                    'disk.identifier_to_device', disk.disk_identifier, system_disks
                )
        else:
            if not path.startswith('/mnt'):
                poolname = path.split('/', 2)[1]
                if gconf.iscsi_pool_avail_threshold:
                    if poolname in zpoollist:
                        poolthreshold[poolname] = int(
                            zpoollist[poolname]['properties']['size']['parsed'] * (
                                gconf.iscsi_pool_avail_threshold / 100.0
                            )
                        )
                if extent.iscsi_target_extent_avail_threshold:
                    zvolname = path.split('/', 1)[1]
                    zfslist = middleware.call_sync('pool.dataset.query', [('id', '=', zvolname)])
                    if zfslist and zfslist[0]['type'] == 'VOLUME':
                        lunthreshold = int(zfslist[0]['volsize']['parsed'] *
                                           (extent.iscsi_target_extent_avail_threshold / 100.0))
                path = '/dev/' + path
            else:
                if extent.iscsi_target_extent_avail_threshold and os.path.exists(path):
                    try:
                        stat = os.stat(path)
                        lunthreshold = int(stat.st_size *
                                           (extent.iscsi_target_extent_avail_threshold / 100.0))
                    except OSError:
                        pass
        addline('lun "%s" {\n' % extent.iscsi_target_extent_name)
        addline('\tctl-lun "%d"\n' % (extent.id - 1))
        size = extent.iscsi_target_extent_filesize
        addline('\tpath "%s"\n' % path)
        addline('\tblocksize "%s"\n' % extent.iscsi_target_extent_blocksize)
        if extent.iscsi_target_extent_pblocksize:
            addline('\toption "pblocksize" "0"\n')
        addline('\tserial "%s"\n' % (extent.iscsi_target_extent_serial, ))
        padded_serial = extent.iscsi_target_extent_serial
        if not extent.iscsi_target_extent_xen:
            for i in range(31 - len(extent.iscsi_target_extent_serial)):
                padded_serial += ' '
        addline('\tdevice-id "iSCSI Disk      %s"\n' % padded_serial)
        if size != '0':
            if size.endswith('B'):
                size = size.strip('B')
            addline('\t\tsize "%s"\n' % size)

        # We can't change the vendor name of existing
        # LUNs without angering VMWare, but we can
        # use the right names going forward.
        addline(f'\toption "vendor" "{extent.iscsi_target_extent_vendor}"\n')
        addline('\toption "product" "iSCSI Disk"\n')
        addline('\toption "revision" "0123"\n')
        addline('\toption "naa" "%s"\n' % extent.iscsi_target_extent_naa)
        addline(f'\toption "serseq" "{"on" if extents[extent.id]["serseq"] else "off"}"\n')
        if extent.iscsi_target_extent_insecure_tpc:
            addline('\toption "insecure_tpc" "on"\n')
            if lunthreshold:
                addline('\toption "avail-threshold" "%s"\n' % lunthreshold)
        if poolname is not None and poolname in poolthreshold:
            addline('\toption "pool-avail-threshold" "%s"\n' % poolthreshold[poolname])
        if extent.iscsi_target_extent_rpm == 'Unknown':
            addline('\toption "rpm" "0"\n')
        elif extent.iscsi_target_extent_rpm == 'SSD':
            addline('\toption "rpm" "1"\n')
        else:
            addline('\toption "rpm" "%s"\n' % extent.iscsi_target_extent_rpm)
        if extent.iscsi_target_extent_ro:
            addline('\toption "readonly" "on"\n')
        addline('}\n')
        addline('\n')

    # Generate the target section
    target_basename = gconf.iscsi_basename
    for target in middleware.call_sync('datastore.query', 'services.iSCSITarget'):
        target = Struct(target)

        authgroups = {}
        for grp in middleware.call_sync('datastore.query', 'services.iscsitargetgroups',
                                        [('iscsi_target', '=', target.id)]):
            grp = Struct(grp)
            if grp.iscsi_target_authgroup:
                auth_list = [
                    Struct(i)
                    for i in middleware.call_sync('datastore.query', 'services.iSCSITargetAuthCredential',
                                                  [('iscsi_target_auth_tag', '=', grp.iscsi_target_authgroup)])
                ]
            else:
                auth_list = []
            agname = 'ag4tg%d_%d' % (target.id, grp.id)
            if auth_group_config(auth_tag=agname,
                                 auth_list=auth_list,
                                 auth_type=grp.iscsi_target_authtype,
                                 initiator=grp.iscsi_target_initiatorgroup):
                authgroups[grp.id] = agname
        if (target.iscsi_target_name.startswith('iqn.') or
                target.iscsi_target_name.startswith('eui.') or
                target.iscsi_target_name.startswith('naa.')):
            addline('target "%s" {\n' % target.iscsi_target_name)
        else:
            addline('target "%s:%s" {\n' % (target_basename, target.iscsi_target_name))
        if target.iscsi_target_alias:
            addline('\talias "%s"\n' % target.iscsi_target_alias)
        elif target.iscsi_target_name:
            addline('\talias "%s"\n' % target.iscsi_target_name)

        for fctt in middleware.call_sync('datastore.query', 'services.fibrechanneltotarget',
                                         [('fc_target', '=', target.id)]):
            fctt = Struct(fctt)
            addline('\tport "%s"\n' % fctt.fc_port)

        for grp in middleware.call_sync('datastore.query', 'services.iscsitargetgroups',
                                        [('iscsi_target', '=', target.id)]):
            grp = Struct(grp)
            agname = authgroups.get(grp.id) or 'no-authentication'
            if gconf.iscsi_alua:
                addline('\tportal-group "pg%dA" "%s"\n' % (grp.iscsi_target_portalgroup.iscsi_target_portal_tag,
                                                           agname))
                addline('\tportal-group "pg%dB" "%s"\n' % (grp.iscsi_target_portalgroup.iscsi_target_portal_tag,
                                                           agname))
            else:
                addline('\tportal-group "pg%d" "%s"\n' % (grp.iscsi_target_portalgroup.iscsi_target_portal_tag,
                                                          agname))
        addline('\n')
        used_lunids = [
            o['iscsi_lunid']
            for o in middleware.call_sync('datastore.query', 'services.iscsitargettoextent',
                                          [('iscsi_target', '=', target.id),
                                           ('iscsi_lunid', '!=', None)])
        ]
        cur_lunid = 0
        for t2e in middleware.call_sync('datastore.query', 'services.iscsitargettoextent',
                                        [('iscsi_target', '=', target.id)],
                                        {'order_by': ['nulls_last:iscsi_lunid']}):
            t2e = Struct(t2e)
            if not t2e.iscsi_extent.iscsi_target_extent_enabled or t2e.iscsi_extent.id in locked_extents:
                # Skip adding extents to targets which are not enabled or are using locked zvols
                continue
            if t2e.iscsi_lunid is None:
                while cur_lunid in used_lunids:
                    cur_lunid += 1
                addline('\tlun "%s" "%s"\n' % (cur_lunid,
                                               t2e.iscsi_extent.iscsi_target_extent_name))
                cur_lunid += 1
            else:
                addline('\tlun "%s" "%s"\n' % (t2e.iscsi_lunid,
                                               t2e.iscsi_extent.iscsi_target_extent_name))
        addline('}\n\n')

    # Write out the CTL config file
    with open(os.open(ctl_config, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), 'w') as fh:
        for line in cf_contents:
            fh.write(line)

    # Write out the CTL config file with redacted CHAP passwords
    with open(os.open(ctl_config_shadow, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), 'w') as fh:
        for line in cf_contents_shadow:
            fh.write(line)


def set_ctl_ha_peer(middleware):

    def set_sysctl(sysctl_key, value):
        cp = subprocess.run(["sysctl", f"{sysctl_key}={value}"], stderr=subprocess.PIPE)
        if cp.returncode:
            middleware.logger.error(
                "Failed to set sysctl '%s' to '%s': %s", sysctl, str(value), str(cp.stderr.decode())
            )

    with contextlib.suppress(IndexError):
        if middleware.call_sync("iscsi.global.alua_enabled"):
            node = middleware.call_sync("failover.node")
            # 999 is the port used by ALUA on the heartbeat interface
            # on TrueNAS HA systems. Because of this, we set
            # net.inet.ip.portrange.lowfirst=998 to ensure local
            # websocket connections do not have the opportunity
            # to interfere.
            sysctl.filter("net.inet.ip.portrange.lowfirst")[0].value = 998
            set_sysctl("kern.cam.ctl.ha_peer", "listen 169.254.10.1" if node == "A" else "connect 169.254.10.1")
        else:
            set_sysctl("kern.cam.ctl.ha_peer", "")


def render(service, middleware):
    main(middleware)
    if middleware.call_sync('failover.licensed'):
        set_ctl_ha_peer(middleware)
