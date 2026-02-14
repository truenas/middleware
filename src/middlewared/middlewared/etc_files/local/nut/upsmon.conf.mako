<%
	import re

	from middlewared.plugins.ups.utils import UPS_POWERDOWN_FLAG_FILE
	ups_config = middleware.call_sync('ups.config')
	user = re.sub(r'([#$])', r'\\\1', ups_config.monuser)
	for field in filter(
		lambda f: not getattr(ups_config, f),
		['monpwd', 'identifier', 'mode', 'monuser']
	):
		middleware.logger.debug(f'UPSMON: {field} field empty, upsmon will fail to start.')
	ident = ups_config.complete_identifier
	xseries = (middleware.call_sync('truenas.get_chassis_hardware')).startswith('TRUENAS-X')
	if not ups_config.shutdowncmd and not xseries:
            shutdown_cmd = '/sbin/shutdown -P now'
	else:
            shutdown_cmd = ups_config.shutdowncmd or ''
%>\
MONITOR ${ident} 1 ${user} ${ups_config.monpwd} ${ups_config.mode}
NOTIFYCMD ${"/usr/sbin/upssched"}
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
% if ups_config.powerdown:
POWERDOWNFLAG ${UPS_POWERDOWN_FLAG_FILE}
% endif
HOSTSYNC ${ups_config.hostsync}
% if ups_config.nocommwarntime:
NOCOMMWARNTIME ${ups_config.nocommwarntime}
% endif
