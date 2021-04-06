<%
    import os

    from collections import defaultdict

    global_config = middleware.call_sync('iscsi.global.config')
    targets = middleware.call_sync('iscsi.target.query')
    extents = {d['id']: d for d in middleware.call_sync('iscsi.extent.query', [['enabled', '=', True]])}
    portals = {d['id']: d for d in middleware.call_sync('iscsi.portal.query')}
    initiators = {d['id']: d for d in middleware.call_sync('iscsi.initiator.query')}
    authenticators = defaultdict(list)
    for auth in middleware.call_sync('iscsi.auth.query'):
        authenticators[auth['tag']].append(auth)

    associated_targets = defaultdict(list)
    for a_tgt in filter(
        lambda a: a['extent'] in extents and not extents[a['extent']]['locked'],
        middleware.call_sync('iscsi.targetextent.query')
    ):
        associated_targets[a_tgt['target']].append(a_tgt)

    # Let's map extents to respective ios
    extents_io = {'vdisk_fileio': [], 'vdisk_blockio': [], 'dev_disk': []}
    for extent in extents.values():
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
            middleware.logger.debug(
                'Skipping generation of extent %r as the underlying resource does not exist', extent['name']
            )
            continue

        extents_io[extents_io_key].append(extent)

        extent['t10_dev_id'] = extent['serial']
        if not extent['xen']:
            extent['t10_dev_id'] = extent['serial'].ljust(31 - len(extent['serial']), ' ')

    # FIXME: SSD is not being reflected in the initiator, please look into it
    # FIXME: Authorized networks for initiators has not been implemented yet, please look for alternatives in SCST

    target_hosts = middleware.call_sync('iscsi.host.get_target_hosts')
    hosts_iqns = middleware.call_sync('iscsi.host.get_hosts_iqns')
%>\
% for handler in filter(lambda k: extents_io[k], extents_io):
HANDLER ${handler} {
%   for extent in extents_io[handler]:
    DEVICE ${extent['name']} {
        filename ${extent['extent_path']}
        blocksize ${extent['blocksize']}
        read_only ${'1' if extent['ro'] else '0'}
        usn ${extent['serial']}
        naa_id ${extent['naa']}
        prod_id "iSCSI Disk"
%       if extent['rpm'] != 'SSD':
        rotational ${extent['rpm']}
%       endif
        t10_vend_id ${extent['vendor']}
        t10_dev_id ${extent['t10_dev_id']}
    }

%   endfor
}
% endfor

TARGET_DRIVER iscsi {
    enabled 1
## We are supposed to set iSNS server here but unfortunately that is not working
## An issue has been opened with scst regarding that and duplicating of target reporting on each new portal
## https://sourceforge.net/p/scst/tickets/38/ ( let's please fix this once we hear back from them )

<%def name="retrieve_luns(target_id, spacing='')">
    % for associated_target in associated_targets[target_id]:
        ${spacing}LUN ${associated_target['lunid']} ${extents[associated_target['extent']]['name']}
    % endfor
</%def>\
% for target in targets:
    TARGET ${global_config['basename']}:${target['name']} {
<%
    # SCST does not allow us to set authentication at a group level, so it is going to be set at
    # target level which we are moving forward with right now. Also for mutual-chap, we can only set
    # one user which the initiator can authenticate on it's end. So if any group in the target
    # desires mutual chap, we take the first one and use it's peer credentials
    mutual_chap = None
    chap_users = set()
    initiator_portal_access = set()
    has_per_host_access = False
    for host in target_hosts[target['id']]:
        for iqn in hosts_iqns[host['id']]:
            initiator_portal_access.add(f'{iqn}\#{host["ip"]}')
            has_per_host_access = True
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
                address = (f'[{addr["ip"]}]' if ':' in addr['ip'] else addr['ip'])
                # FIXME: SCST does not seem to respect port values for portals, please look for alternatives

            group_initiators = initiators[group['initiator']]['initiators'] if group['initiator'] else []
            if not has_per_host_access:
                group_initiators = group_initiators or ['*']
            for initiator in group_initiators:
                initiator_portal_access.add(f'{initiator}\#{address}')
%>\
%   if associated_targets:
        enabled 1
        per_portal_acl 1
%   endif
%   for chap_auth in chap_users:
        IncomingUser "${chap_auth}"
%   endfor
%   if mutual_chap:
        OutgoingUser "${mutual_chap}"
%   endif

        GROUP security_group {
%   for access_control in initiator_portal_access:
            INITIATOR ${access_control}
%   endfor
${retrieve_luns(target['id'], ' ' * 4)}\
        }
    }
% endfor
}
