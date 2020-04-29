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
	for a_tgt in filter(lambda a: a['extent'] in extents, middleware.call_sync('iscsi.targetextent.query')):
		associated_targets[a_tgt['target']].append(a_tgt)

	# Let's map extents to respective ios
	extents_io = {'vdisk_fileio': [], 'vdisk_blockio': [], 'dev_disk': []}
	for extent in extents.values():
		if extent['type'] == 'DISK':
			extent['extent_path'] = os.path.join('/dev', extent['disk'])
			extents_io['vdisk_blockio'].append(extent)
			# dev_disk is pass-through which we would be using for disks
			# FIXME: It is however showing kernel dumps
			# So for now we use blockio for disks as well
		else:
			extent['extent_path'] = extent['path']
			extents_io['vdisk_fileio'].append(extent)
	# FIXME: SSD is not being reflected in the initiator, please look into it
	# FIXME: Authorized networks for initiators has not been implemented yet, please look for alternatives in SCST
%>\
% for handler in filter(lambda k: extents_io[k], extents_io):
HANDLER ${handler} {
%	for extent in extents_io[handler]:
	DEVICE ${extent['name']} {
		filename ${extent['extent_path']}
		blocksize ${extent['blocksize']}
		read_only ${'1' if extent['ro'] else '0'}
		usn ${extent['serial']}
		naa_id ${extent['naa']}
		prod_id "iSCSI Disk"
%		if extent['rpm'] != 'SSD':
		rotational ${extent['rpm']}
%		endif
	}

%	endfor
}
% endfor

TARGET_DRIVER iscsi {
	enabled 1

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
	for group in filter(lambda g: g['authmethod'] != 'NONE' and authenticators[group['auth']], target['groups']):
		auth_list = authenticators[group['auth']]
		if group['CHAP_MUTUAL'] and not mutual_chap:
			mutual_chap = f'{auth_list[0]["peeruser"]} {auth_list[0]["peersecret"]}'

		chap_users.update(f'{auth["user"]} {auth["secret"]}' for auth in auth_list)
%>\
%	if associated_targets:
		enabled 1
		per_portal_acl 1
%	endif
%	for chap_auth in chap_users:
		IncomingUser "${chap_auth}"
%	endfor
%	if mutual_chap:
		OutgoingUser "${mutual_chap}"
%	endif

%	for group in target['groups']:
<%
	addresses = []
	for addr in portals[group['portal']]['listen']:
		if addr['ip'] == '0.0.0.0':
			# SCST uses wildcard patterns
			# FIXME: Please investigate usage of ipv6 patterns
			# https://github.com/truenas/scst/blob/e945943861687d16ae0415207306f75a55bcfd2b/iscsi-scst/usr/target.c#L139-L138
			addresses = [{**addr, 'ip': '*'}]
			break
		addresses.append({**addr, 'ip': f'[{addr["ip"]}]' if ':' in addr['ip'] else addr['ip']})
		# FIXME: SCST does not seem to respect port values for portals, please look for alternatives
		# Refer to above git link please for this fixme
%>\
%       for index, addr in enumerate(addresses):
		GROUP ${target['name']}_portal_${group['portal']}_${index} {
%			for initiator in (initiators[group['initiator']]['initiators'] or ['*']):
			INITIATOR ${initiator}\#${addr['ip']}
%			endfor
${retrieve_luns(target['id'], '\t')}\
		}
%       endfor
%	endfor
	}
% endfor
}
