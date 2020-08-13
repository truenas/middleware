<%
	rsyncd_config = middleware.call_sync('rsyncd.config')	
	mods = middleware.call_sync('rsyncmod.query', [['enabled', '=', True]])
%>\
use chroot = yes
max connections = 4
pid file = /var/run/rsyncd.pid
% if rsyncd_config['port'] != 873:
port = ${rsyncd_config['port']}
% endif
${rsyncd_config['auxiliary']}
% for mod in mods:
<%
    if mod['locked']:
        middleware.call_sync('rsyncmod.generate_locked_alert', mod['id'])
        continue
%>\
[${mod['name']}]
	path = ${mod['path']}
	max connections = ${mod['maxconn']}
	uid = ${mod['user']}
	gid = ${mod['group']}
	% if mod['comment']:
	comment = ${mod['comment']}
	% endif
	% if mod['mode'] == 'RO':
	write only = false
	read only = true
	% elif mod['mode'] == 'WO':
	write only = true
	read only = false
	% elif mod['mode'] == 'RW':
	read only = false
	write only = false
	% endif
	% if mod['hostsallow']:
	hosts allow = ${' '.join(mod['hostsallow'])}
	% endif
	% if mod['hostsdeny']:
	hosts deny = ${' '.join(mod['hostsdeny'])}
	% endif
${mod['auxiliary']}
% endfor
