<%
	import re

	ups_config = middleware.call_sync('ups.config')
	user = re.sub(r'([#="$])', r'\\\1', ups_config['monuser'])
%>\
% if ups_config['rmonitor']:
[${user}]
	password = ${ups_config['monpwd']}
	upsmon master

${ups_config['extrausers']}
% endif
