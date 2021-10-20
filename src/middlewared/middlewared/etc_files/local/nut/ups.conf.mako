<%
	ups_config = middleware.call_sync('ups.config')
	driver = middleware.call_sync('ups.normalize_driver_string', ups_config['driver'])
%>\
[${ups_config['identifier']}]
	${driver}
	port = ${ups_config['port']}
	desc = "${ups_config['description'].replace('"', r'\"')}"
	${ups_config['options']}
