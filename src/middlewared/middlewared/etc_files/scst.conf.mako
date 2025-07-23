<%
    import itertools
    import os
    import time

    from collections import defaultdict
    from pathlib import Path

    from middlewared.service import CallError
    from middlewared.plugins.fc.utils import is_fc_addr, str_to_naa, wwn_as_colon_hex
    from middlewared.plugins.iscsi_.utils import ISCSI_TARGET_PARAMETERS, ISCSI_HA_TARGET_PARAMETERS

    REL_TGT_ID_NODEB_OFFSET = 32000
    REL_TGT_ID_FC_OFFSET = 5000

    global_config = render_ctx['iscsi.global.config']

    def existing_copy_manager_luns():
        luns = {}
        p = Path('/sys/kernel/scst_tgt/targets/copy_manager/copy_manager_tgt/luns')
        if p.is_dir():
            for lun in p.iterdir():
                if lun.is_dir() and lun.name != 'mgmt':
                    link = Path(lun, 'device')
                    if link.is_symlink():
                        target = link.readlink()
                        luns[int(lun.name)] = target.name
        return luns

    def calc_copy_manager_luns(devices, force_insert=False):
        cml = existing_copy_manager_luns()
        # Remove any devices not present
        for key in list(cml):
            if cml[key] not in devices:
                del cml[key]
        if force_insert:
            # Add any devices not yet in cml
            to_add = set(devices) - set(cml.values())
            start_count = 0
            for device in to_add:
                keys = list(cml)
                while start_count in keys:
                    start_count += 1
                cml[start_count] = device
        return cml

    targets = render_ctx['iscsi.target.query']
    extents = {d['id']: d for d in middleware.call_sync('iscsi.extent.query', [['enabled', '=', True]])}
    portals = {d['id']: d for d in middleware.call_sync('iscsi.portal.query')}
    initiators = {d['id']: d for d in middleware.call_sync('iscsi.initiator.query')}
    fcports_by_target_id = {d['target']['id']: d for d in render_ctx['fcport.query']}
    fcports_by_port_name = {d['port']: d for d in render_ctx['fcport.query']}
    targets_by_id = {d['id']: d for d in targets}
    authenticators = defaultdict(list)

    discovery_incoming = []
    discovery_outgoing = []
    for auth in render_ctx['iscsi.auth.query']:
        authenticators[auth['tag']].append(auth)
        disc_auth = auth.get('discovery_auth')
        if disc_auth in ['CHAP', 'CHAP_MUTUAL']:
            user = auth.get('user')
            secret = auth.get('secret')
            if user and secret:
                discovery_incoming.append(f'{user} {secret}')
        if disc_auth in ['CHAP_MUTUAL']:
            user = auth.get('peeruser')
            secret = auth.get('peersecret')
            if user and secret:
                discovery_outgoing.append(f'{user} {secret}')

    # Populate this below
    fc_host_by_port_name = {}

    def ha_node_wwpn_for_fcport_or_fchost(fcport):
        if not is_ha or render_ctx['failover.node'] == 'A':
            return wwn_as_colon_hex(fcport['wwpn'])
        elif render_ctx['failover.node'] == 'B':
            return wwn_as_colon_hex(fcport['wwpn_b'])

    def ha_node_wwpn_for_target(target, node):
        if target['id'] in fcports_by_target_id:
            fcport = fcports_by_target_id[target['id']]
            if not is_ha or node == 'A':
                return wwn_as_colon_hex(fcport['wwpn'])
            elif node == 'B':
                return wwn_as_colon_hex(fcport['wwpn_b'])

    def is_iscsi_target(target):
        return target['mode'] in ['ISCSI', 'BOTH']

    def is_fc_target(target):
        return target['mode'] in ['FC', 'BOTH']

    def fcport_to_target(fcport):
        try:
            return targets_by_id[fcport['target']['id']]
        except KeyError:
            return None

    def fcport_to_parent_host(fcport):
        if '/' in fcport['port']:
            parent_port_name = fcport['port'].split('/')[0]
            if parent_fcport := fcports_by_port_name.get(parent_port_name):
                return ha_node_wwpn_for_fcport_or_fchost(parent_fcport)
            if parent_fchost := fc_host_by_port_name.get(parent_port_name):
                return ha_node_wwpn_for_fcport_or_fchost(parent_fchost)

    def fc_initiator_access_for_target(target):
        initiator_access = set()
        for group in target['groups']:
            group_initiators = initiators[group['initiator']]['initiators'] if group['initiator'] else []
            for initiator in group_initiators:
                if wwn := wwn_as_colon_hex(initiator):
                    initiator_access.add(wwn)
        return initiator_access

    if render_ctx['fc.capable']:
        fc_host_by_port_name = {x['alias']: x for x in middleware.call_sync('fc.fc_host.query')}
        # Physical devices are added to the config automatically.  We want to
        # identify any that are not being used and select a rel_tgt_id in the
        # 10K range for them.
        ports_in_use = middleware.call_sync('fc.fc_hosts', [['physical', '=', True]], {'select': ['port_name']})
        physical_naa = {str_to_naa(entry['port_name']) for entry in ports_in_use}
        used_physical_naa = set()
        for entry in render_ctx['fcport.query']:
            if '/' not in entry['port']:
                for key in ['wwpn', 'wwpn_b']:
                    if naa := entry.get(key):
                        used_physical_naa.add(naa)
        unused_physical = sorted([wwn_as_colon_hex(naa) for naa in (physical_naa - used_physical_naa)])

    # There are several changes that must occur if ALUA is enabled,
    # and these are different depending on whether this is the
    # MASTER node, or BACKUP node.
    #
    # MASTER:
    # - publish additional internal targets, only accessible on the private IP
    #
    # BACKUP:
    # - login to these internal targets
    # - access them in dev_disk HANDLER
    # - Add them to copy_manager
    # - reexport them on the same IQNs as the master, but with different
    #   rel_tgt_id.
    #
    # BOTH:
    # - Write a DEVICE_GROUP section with two TARGET_GROUPs
    # - TARGET GROUPs and rel_tgt_id are tied to the controller,
    #   *not* to whether it is currently the MASTER or BACKUP
    # - clustered_extents is used to prevent cluster_mode from being
    #   enabled on entents at startup.  We will have to explicitly
    #   write 1 to cluster_mode elsewhere.
    is_ha = render_ctx['failover.licensed']
    alua_enabled = render_ctx['iscsi.global.alua_enabled']
    failover_status = render_ctx['failover.status']
    node = render_ctx['failover.node']
    failover_virtual_aliases = []
    if alua_enabled:
        listen_ip_choices = middleware.call_sync('iscsi.portal.listen_ip_choices')
        for interface in middleware.call_sync('interface.query', [('failover_virtual_aliases', '!=', [])]):
            for addr in interface['failover_virtual_aliases']:
                if 'address' in addr:
                    failover_virtual_aliases.append(addr['address'])

    standby_node_requires_reload = False
    fix_cluster_mode = []
    cluster_mode_targets = []
    cluster_mode_luns = {}
    clustered_extents = set()
    active_extents = []
    standby_write_empty_config = False
    skipped_wwpns = set()
    if failover_status == "MASTER":
        local_ip = middleware.call_sync("failover.local_ip")
        dlm_ready = middleware.call_sync("dlm.node_ready")
        if alua_enabled:
            active_extents = middleware.call_sync("iscsi.extent.active_extents")
            clustered_extents = set(middleware.call_sync("iscsi.target.clustered_extents"))
            cluster_mode_targets = middleware.call_sync("iscsi.target.cluster_mode_targets")
    elif failover_status == "BACKUP":
        if alua_enabled:
            if standby_write_empty_config := middleware.call_sync("iscsi.alua.standby_write_empty_config"):
                logged_in_targets = {}
            else:
                retries = 5
                while retries:
                    try:
                        logged_in_targets = middleware.call_sync("iscsi.target.login_ha_targets")
                        break
                    except Exception:
                        # We might just experience a race, so attempt a quick retry
                        time.sleep(1)
                    retries -= 1
                if not retries:
                    middleware.logger.warning('Failed to login HA targets', exc_info=True)
                    logged_in_targets = {}
                    standby_node_requires_reload = True
                try:
                    _cmt_cml = middleware.call_sync(
                        'failover.call_remote', 'iscsi.target.cluster_mode_targets_luns', [], {'raise_connect_error': False}
                    )
                except Exception:
                    middleware.logger.warning('Unhandled error contacting remote node', exc_info=True)
                    standby_node_requires_reload = True
                else:
                    if _cmt_cml is not None:
                        cluster_mode_targets, cluster_mode_luns = _cmt_cml
                clustered_extents = set(middleware.call_sync("iscsi.target.clustered_extents"))
        else:
            middleware.call_sync("iscsi.target.logout_ha_targets")
            targets = []
            extents = {}
            portals = {}
            initiators = {}

    nodes = {"A" : {"other" : "B", "group_id" : 101},
             "B" : {"other" : "A", "group_id" : 102}}
    try:
        other_node = nodes[node]['other']
    except KeyError:
        # Non-HA
        other_node = 'MANUAL'

    # Let's map extents to respective ios
    all_extent_names = []
    missing_extents = []
    extents_io = {'vdisk_fileio': [], 'vdisk_blockio': []}
    for extent in extents.values():
        extent['name'] = extent['name'].replace('.', '_').replace('/', '-')  # CORE ctl device names are incompatible with SCALE SCST
        if extent['locked']:
            middleware.logger.debug(
                'Skipping generation of extent %r as the underlying resource is locked', extent['name']
            )
            middleware.call_sync('iscsi.extent.generate_locked_alert', extent['id'])
            continue

        if extent['type'] == 'DISK':
            extent['extent_path'] = os.path.join('/dev', extent['disk'])
            extents_io_key = 'vdisk_blockio'
        else:
            extent['extent_path'] = extent['path']
            extents_io_key = 'vdisk_fileio'

        if not os.path.exists(extent['extent_path']):
            # We're going to permit the extent if ALUA is enabled and we're the BACKUP node
            if not alua_enabled or failover_status != "BACKUP":
                middleware.logger.debug(
                    'Skipping generation of extent %r as the underlying resource does not exist', extent['name']
                )
                missing_extents.append(extent['id'])
                continue

        extents_io[extents_io_key].append(extent)
        all_extent_names.append(extent['name'])

        extent['t10_dev_id'] = extent['serial']
        if not extent['xen']:
            extent['t10_dev_id'] = extent['serial'].ljust(31 - len(extent['serial']), ' ')

    associated_targets = defaultdict(list)
    # On ALUA BACKUP node (only) we will include associated_targets even if underlying device is missing
    if failover_status == 'BACKUP':
        if alua_enabled:
            for a_tgt in filter(
                lambda a: a['extent'] in extents and not extents[a['extent']]['locked'],
                middleware.call_sync('iscsi.targetextent.query')
            ):
                associated_targets[a_tgt['target']].append(a_tgt)
        # If ALUA not enabled then keep associated_targets as empty
    else:
        for a_tgt in filter(
            lambda a: a['extent'] in extents and not extents[a['extent']]['locked'] and a['extent'] not in missing_extents,
            middleware.call_sync('iscsi.targetextent.query')
        ):
            associated_targets[a_tgt['target']].append(a_tgt)

    # FIXME: SSD is not being reflected in the initiator, please look into it

    if alua_enabled and failover_status == "BACKUP":
        cml = calc_copy_manager_luns(list(itertools.chain.from_iterable([x for x in logged_in_targets.values() if x is not None])), True)
    else:
        cml = calc_copy_manager_luns(all_extent_names)

    def set_active_lun_to_cluster_mode(extentname):
        if extentname in active_extents and extentname in clustered_extents:
            return True
        return False

    def set_standby_lun_to_cluster_mode(device, targetname):
        if device in clustered_extents:
            if targetname in cluster_mode_luns and int(device.split(':')[-1]) in cluster_mode_luns[targetname]:
                return True
        return False

    def set_standy_target_to_enabled(targetname):
        devices = logged_in_targets.get(targetname, [])
        if devices:
            if set(devices).issubset(clustered_extents):
                return True
        return False

    def option_value(v):
        if isinstance(v, bool):
            return "Yes" if v else "No"
        return v
%>\
##
## If we are on a HA system then write out a cluster name, we'll hard-code
## it to "HA"
##
% if is_ha:
cluster_name HA
% endif
##
## Write "HANDLER dev_disk" section on any HA-capable system (to force the
## kernel module to get loaded on SCST startup), but only populate it on the
## ALUA BACKUP node.
##
% if is_ha:
HANDLER dev_disk {
%     if alua_enabled and failover_status == "BACKUP":
%         for name, devices in logged_in_targets.items():
%             if devices:
%                 for device in devices:

        DEVICE ${device} {
## We will only enter cluster_mode here if two conditions are satisfied:
## 1. We are already in cluster_mode, AND
## 2. The corresponding LUN on the MASTER is in cluster_mode
## Note we use a similar check to determine whether the target will be enabled.
%                 if set_standby_lun_to_cluster_mode(device, name):
            cluster_mode 1
%                 else:
<%
    fix_cluster_mode.append(device)
%>\
            cluster_mode 0
%                 endif
        }
%                 endfor
%             endif
%         endfor
%     endif
}
% endif
##
## Write "TARGET_DRIVER copy_manager" section as otherwise CM
## can get confused wrt LUNs present when a new target is
## added (although no problem if SCST is restarted after all
## configuration changes have been made).
##
% if len(cml):
TARGET_DRIVER copy_manager {
        TARGET copy_manager_tgt {
%       for key in sorted(cml):
                LUN ${key} ${cml[key]}
%       endfor
        }
}
% endif
##

####################################################################################
##
## Devices
##
####################################################################################
% for handler in extents_io:
HANDLER ${handler} {
%   for extent in extents_io[handler]:
    DEVICE ${extent['name']} {
        filename ${extent['extent_path']}
        blocksize ${extent['blocksize']}
%       if extent['pblocksize']:
        lb_per_pb_exp 0
%       endif
        read_only ${'1' if extent['ro'] else '0'}
        usn ${extent['serial']}
        naa_id ${extent['naa']}
        prod_id "${extent['product_id']}"
%       if extent['rpm'] != 'SSD':
        rotational 1
%       else:
        rotational 0
%       endif
        t10_vend_id ${extent['vendor']}
        t10_dev_id ${extent['t10_dev_id']}
%       if failover_status == "MASTER" and alua_enabled and dlm_ready:
%       if set_active_lun_to_cluster_mode(extent['name']):
        cluster_mode 1
%       else:
        cluster_mode 0
%       endif
%       endif
%       if failover_status == "BACKUP" and alua_enabled:
        active 0
%       endif
%       if handler == 'vdisk_blockio':
        threads_num 32
%       endif
    }

%   endfor
}
% endfor

####################################################################################
##
## iSCSI targets
##
####################################################################################
TARGET_DRIVER iscsi {
%   if node == 'A':
    internal_portal 169.254.10.1
%   elif node == 'B':
    internal_portal 169.254.10.2
%   endif
%   for chap_auth in discovery_incoming:
    IncomingUser "${chap_auth}"
%   endfor
%   if discovery_outgoing:
    OutgoingUser "${discovery_outgoing[0]}"
%   endif
    enabled 1
    link_local 0
## Currently SCST only supports one iSNS server
% if global_config['isns_servers']:
    iSNSServer ${global_config['isns_servers'][0]}
% endif
## We are supposed to set iSNS server here but unfortunately that is not working
## An issue has been opened with scst regarding that and duplicating of target reporting on each new portal
## https://sourceforge.net/p/scst/tickets/38/ ( let's please fix this once we hear back from them )

<%def name="retrieve_luns(target_id, spacing='')">
    % for associated_target in associated_targets[target_id]:
        ${spacing}LUN ${associated_target['lunid']} ${extents[associated_target['extent']]['name']}
    % endfor
</%def>\
% for idx, target in enumerate(targets, start=1):
%if is_iscsi_target(target):
    TARGET ${global_config['basename']}:${target['name']} {
<%
    # SCST does not allow us to set authentication at a group level, so it is going to be set at
    # target level which we are moving forward with right now. Also for mutual-chap, we can only set
    # one user which the initiator can authenticate on it's end. So if any group in the target
    # desires mutual chap, we take the first one and use it's peer credentials
    alias = target.get('alias')
    mutual_chap = None
    chap_users = set()
    iscsi_initiator_portal_access = set()
    for group in target['groups']:
        if group['authmethod'] != 'NONE' and authenticators[group['auth']]:
            auth_list = authenticators[group['auth']]
            if group['authmethod'] == 'CHAP_MUTUAL' and not mutual_chap:
                mutual_chap = f'{auth_list[0]["peeruser"]} {auth_list[0]["peersecret"]}'

            chap_users.update(f'{auth["user"]} {auth["secret"]}' for auth in auth_list)

        for addr in portals[group['portal']]['listen']:
            if addr['ip'] in ('0.0.0.0', '::'):
                # SCST uses wildcard patterns
                # https://github.com/truenas/scst/blob/e945943861687d16ae0415207306f75a55bcfd2b/iscsi-scst/usr/target.c#L139-L138
                address = '*'
            else:
                # In an ALUA config, we may have selected the int_vip.  If so just use
                # the IP pertainng to this node.
                address = addr['ip']
                if alua_enabled and address in failover_virtual_aliases and address in listen_ip_choices and '/' in listen_ip_choices[address]:
                    pair = listen_ip_choices[address].split('/')
                    address = pair[0] if node == 'A' else pair[1]

            for initiator in ((initiators[group['initiator']]['initiators'] if group['initiator'] else []) or ['*']):
                if not is_fc_addr(initiator):
                    iscsi_initiator_portal_access.add(f'{initiator}\#{address}')
%>\
%   if associated_targets.get(target['id']):
##
## For ALUA rel_tgt_id is tied to controller, if not ALUA write it anyway
## to avoid it changing when ALUA is toggled.
##
%       if alua_enabled:
%           if node == "A":
        rel_tgt_id ${target['rel_tgt_id']}
%           endif
%           if node == "B":
        rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_NODEB_OFFSET}
%           endif
%       else:
        rel_tgt_id ${target['rel_tgt_id']}
%       endif
##
## For ALUA target is enabled if MASTER, disabled for BACKUP
##
%       if alua_enabled:
%           if failover_status == "MASTER":
        enabled 1
%           elif failover_status == "BACKUP" and set_standy_target_to_enabled(target['name']):
        enabled 1
%           else:
        enabled 0
%           endif
%       else:
        enabled 1
%       endif
##
## per_portal_acl always 1
##
        per_portal_acl 1
%   else:
## If no associated targets then disable
        enabled 0
%   endif
##
## alias
##
%   if alias:
        alias "${alias}"
%   endif
%   for chap_auth in chap_users:
        IncomingUser "${chap_auth}"
%   endfor
%   if mutual_chap:
        OutgoingUser "${mutual_chap}"
%   endif
##
## Add target parameters (if not None value)
##
% for k,v in target.get('iscsi_parameters', {}).items():
%   if k in ISCSI_TARGET_PARAMETERS and v is not None:
        ${k} ${option_value(v)}
%   endif
% endfor

        GROUP security_group {
%   for access_control in iscsi_initiator_portal_access:
            INITIATOR ${access_control}
%   endfor
##
%   if alua_enabled and failover_status == "BACKUP":
<%
    devices = logged_in_targets.get(target['name'], None)
%>\
%       if devices:
%           for device in devices:
            LUN ${device.split(':')[-1]} ${device}
%           endfor
%       endif
%   else:
${retrieve_luns(target['id'], ' ' * 4)}\
%   endif
        }
    }
% endif  ## is_iscsi_target
% endfor
##
## For the master in HA ALUA write out additional targets that will only be accessible
## from the peer node.  These will have the flipped rel_tgt_id
##
% if alua_enabled and failover_status == "MASTER":
%     for idx, target in enumerate(targets, start=1):
    TARGET ${global_config['basename']}:HA:${target['name']} {
        allowed_portal ${local_ip}
%       if node == "A":
        rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_NODEB_OFFSET}
%       endif
%       if node == "B":
        rel_tgt_id ${target['rel_tgt_id']}
%       endif
## Mimic the enabled behavior of the base target.  Only enable if have associated extents
%   if associated_targets.get(target['id']):
        enabled 1
%   else:
        enabled 0
%   endif
        forward_dst 1
        aen_disabled 1
        forwarding 1
##
## Add target parameters (if not None value)
##
% for k,v in target.get('iscsi_parameters', {}).items():
%   if k in ISCSI_HA_TARGET_PARAMETERS and v is not None:
        ${k} ${option_value(v)}
%   endif
% endfor
${retrieve_luns(target['id'],'')}\
    }
%     endfor
% endif
}

####################################################################################
##
## Fibre Channel targets
##
####################################################################################
% if render_ctx['fc.capable']:
%   if render_ctx['fcport.query']:
TARGET_DRIVER qla2x00t {
##
## Write out any unused physical portals
##
% for rel_tgt_id, wwpn in enumerate(unused_physical, start=10000):

    TARGET ${wwpn} {
        rel_tgt_id ${rel_tgt_id}
        enabled 0
    }
% endfor

## How we populate the FC targets depends on the configuration / node status
% if is_ha:
##
## HA configuration
##
% for fcport in render_ctx['fcport.query']:
% if alua_enabled:
##    ALUA enabled - write out the target for this node
<%
    wwpn = ha_node_wwpn_for_fcport_or_fchost(fcport)
    target = fcport_to_target(fcport)
    fc_initiator_access = fc_initiator_access_for_target(target)
    parent_host = fcport_to_parent_host(fcport)
    skip_wwpn = standby_write_empty_config and "/" in fcport['port']
    if skip_wwpn:
        skipped_wwpns.add(wwpn)
%>\
% if skip_wwpn:
<% continue %>
% endif
% if wwpn and target:
    TARGET ${wwpn} {
% if parent_host:
        node_name ${parent_host}
        parent_host ${parent_host}
% endif  ## parent_host
% if node == "A":
        rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET}
% endif
% if node == "B":
        rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET + REL_TGT_ID_NODEB_OFFSET}
% endif
% if failover_status == "MASTER":
        enabled 1
% elif failover_status == "BACKUP" and set_standy_target_to_enabled(fcport['target']['iscsi_target_name']):
        enabled 1
% else:
        enabled 0
% endif
## Before we write the LUNs, we may write a security_group
% if fc_initiator_access:
        GROUP security_group {
%   for initiator_wwpn in fc_initiator_access:
            INITIATOR ${initiator_wwpn}
%   endfor
% endif  ## if fc_initiator_access
% if failover_status == "MASTER":
        % for associated_target in associated_targets[fcport['target']['id']]:
        LUN ${associated_target['lunid']} ${extents[associated_target['extent']]['name']}
        % endfor
% elif failover_status == "BACKUP":
<%
    devices = logged_in_targets.get(fcport['target']['iscsi_target_name'], None)
%>\
%       if devices:
%       for device in devices:
        LUN ${device.split(':')[-1]} ${device}
%       endfor
%       endif
% endif  ## MASTER / BACKUP
% if fc_initiator_access:
        }
% endif  ## if fc_initiator_access
% endif  ##  wwpn and target
    }
%  else:  ## ALUA
##    ALUA not enabled - only write out the target for this node if MASTER
% if failover_status == "MASTER":
<%
    wwpn = ha_node_wwpn_for_fcport_or_fchost(fcport)
    target = fcport_to_target(fcport)
    fc_initiator_access = fc_initiator_access_for_target(target)
    parent_host = fcport_to_parent_host(fcport)
%>
    % if wwpn and target:
    TARGET ${wwpn} {
% if parent_host:
        node_name ${parent_host}
        parent_host ${parent_host}
% endif  ## parent_host
        rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET}
        enabled 1
## Before we write the LUNs, we may write a security_group
% if fc_initiator_access:
        GROUP security_group {
%   for initiator_wwpn in fc_initiator_access:
            INITIATOR ${initiator_wwpn}
%   endfor
% endif  ## if fc_initiator_access

        % for associated_target in associated_targets[fcport['target']['id']]:
        LUN ${associated_target['lunid']} ${extents[associated_target['extent']]['name']}
        % endfor
% if fc_initiator_access:
        }
% endif  ## if fc_initiator_access
    }
    % endif  ## wwpn and
% endif  ## if MASTER
% endif  ## ALUA (not)
% endfor  ## for fcport
% else:  ## HA
##
## NOT HA - just write out targets
##
% for fcport in render_ctx['fcport.query']:
<%
    wwpn = wwn_as_colon_hex(fcport['wwpn'])
    target = fcport_to_target(fcport)
    parent_host = fcport_to_parent_host(fcport)
%>
    % if wwpn and target:
    TARGET ${wwpn} {
% if parent_host:
        node_name ${parent_host}
        parent_host ${parent_host}
% endif  ## parent_host
        rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET}
        enabled 1
        % for associated_target in associated_targets[fcport['target']['id']]:
        LUN ${associated_target['lunid']} ${extents[associated_target['extent']]['name']}
        % endfor
    }
    % endif  ## wwpn and target
% endfor
%endif
}
%   endif
% endif
##
####################################################################################
##
## Device group
##
####################################################################################
##
## If ALUA is enabled then we will want a section to setup the target portal groups
##
## Since we do NOT split ZFS pools (and their subsequent targets) across controllers
## we can just have one TPG per node.
##   - Controller A will have TPG ID of 101
##   - Controller B will have TPG ID of 102
##
## What is in each TPG depends upon which node is the MASTER and which is the BACKUP
##
## To make the code easier to read we have a different section for MASTER and BACKUP
##
% if alua_enabled:
##
## MASTER
##   - this node is active and contains the targets
##   - other node contains the "HA" targets (rel_tgt_ids 32001,..)
##
%     if failover_status == "MASTER":
DEVICE_GROUP targets {
% for handler in extents_io:
%   for extent in extents_io[handler]:
        DEVICE ${extent['name']}
%   endfor
% endfor

        TARGET_GROUP controller_${node} {
                group_id ${nodes[node]["group_id"]}
                state active

% for target in targets:
% if is_iscsi_target(target):
                TARGET ${global_config['basename']}:${target['name']}
% endif
% if is_fc_target(target):
<% wwpn = ha_node_wwpn_for_target(target, node) %>\
% if wwpn:
                TARGET ${wwpn}
% endif
% endif
% endfor
        }

        TARGET_GROUP controller_${nodes[node]["other"]} {
                group_id ${nodes[nodes[node]["other"]]["group_id"]}
                state nonoptimized

% for target in targets:
                TARGET ${global_config['basename']}:HA:${target['name']}
% if is_fc_target(target):
<% wwpn = ha_node_wwpn_for_target(target, other_node) %>\
% if wwpn:
                TARGET ${wwpn} {
% if other_node == "A":
                    rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET}
% endif
% if other_node == "B":
                    rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET+ REL_TGT_ID_NODEB_OFFSET}
% endif
                }
% endif  ## wwpn
% endif  ## is_fc_target
% endfor  ## target
        }
}
%     endif
##
## BACKUP
##   - this node is nonoptimized
##   - other node contains the "ALT" placeholder targets
##
%     if failover_status == "BACKUP":
DEVICE_GROUP targets {
%         for name, devices in logged_in_targets.items():
%             if devices:
%                 for device in devices:
        DEVICE ${device}
%                 endfor
%             endif
%         endfor

        TARGET_GROUP controller_${nodes[node]["other"]} {
                group_id ${nodes[nodes[node]["other"]]["group_id"]}
                state active

% for idx, target in enumerate(targets, start=1):
% if is_iscsi_target(target):
                TARGET ${global_config['basename']}:alt:${target['name']} {
%     if node == "A":
                   rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_NODEB_OFFSET}
%     endif
%     if node == "B":
                   rel_tgt_id ${target['rel_tgt_id']}
%     endif
                }
% endif  ## is_iscsi_target
% if is_fc_target(target):
<% wwpn = ha_node_wwpn_for_target(target, other_node) %>\
% if wwpn:
                TARGET ${wwpn} {
% if other_node == "A":
                    rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET}
% endif
% if other_node == "B":
                    rel_tgt_id ${target['rel_tgt_id'] + REL_TGT_ID_FC_OFFSET + REL_TGT_ID_NODEB_OFFSET}
% endif
                }
% endif  ## wwpn
% endif  ## is_fc_target
% endfor

        }

        TARGET_GROUP controller_${node} {
                group_id ${nodes[node]["group_id"]}
                state nonoptimized

% for target in targets:
% if is_iscsi_target(target):
                TARGET ${global_config['basename']}:${target['name']}
% endif  ## is_iscsi_target
% if is_fc_target(target):
<% wwpn = ha_node_wwpn_for_target(target, node) %>\
% if wwpn and not wwpn in skipped_wwpns:
                TARGET ${wwpn}
% endif  ## wwpn
% endif  ## is_fc_target
% endfor ## target
        }

}
%     endif
% endif
<%
    if standby_node_requires_reload:
        middleware.call_sync('iscsi.alua.standby_delayed_reload')
    elif fix_cluster_mode:
        middleware.call_sync('iscsi.alua.standby_fix_cluster_mode', fix_cluster_mode)
%>
