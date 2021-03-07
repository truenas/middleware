<%
	import re

	ups_config = middleware.call_sync('ups.config')
	user = re.sub(r'([#$])', r'\\\1', ups_config['monuser'])
	powerdown = '/etc/killpower' if ups_config['powerdown'] else '/etc/nokillpower'
	for field in filter(
		lambda f: not ups_config[f],
		['monpwd', 'identifier', 'mode', 'monuser']
	):
		middleware.logger.debug(f'UPSMON: {field} field empty, upsmon will fail to start.')
	ident = ups_config['complete_identifier']
	xseries = (middleware.call_sync('truenas.get_chassis_hardware')).startswith('TRUENAS-X')
	if not ups_config['shutdowncmd'] and not xseries:
            shutdown_cmd = f'/sbin/shutdown -{"P" if IS_LINUX else "p" } now'
	else:
            shutdown_cmd = ups_config['shutdowncmd'] or ''
%>\
MONITOR ${ident} 1 ${user} ${ups_config['monpwd']} ${ups_config['mode']}
NOTIFYCMD ${"/usr/sbin/upssched" if IS_LINUX else "/usr/local/sbin/upssched"}
NOTIFYFLAG ONBATT SYSLOG+EXEC
NOTIFYFLAG LOWBATT SYSLOG+EXEC
NOTIFYFLAG ONLINE SYSLOG+EXEC
NOTIFYFLAG COMMBAD SYSLOG+EXEC
NOTIFYFLAG COMMOK SYSLOG+EXEC
NOTIFYFLAG REPLBATT SYSLOG+EXEC
NOTIFYFLAG NOCOMM SYSLOG+EXEC
NOTIFYFLAG FSD SYSLOG+EXEC
NOTIFYFLAG SHUTDOWN SYSLOG+EXEC
SHUTDOWNCMD "${shutdown_cmd}"
POWERDOWNFLAG ${powerdown}
HOSTSYNC ${ups_config['hostsync']}
% if ups_config['nocommwarntime']:
NOCOMMWARNTIME ${ups_config['nocommwarntime']}
% endif
