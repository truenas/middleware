<%
	from middlewared.plugins.ups.utils import normalize_driver_string
	ups_config = render_ctx['ups.config']
	driver = normalize_driver_string(ups_config.driver)
%>\
[${ups_config.identifier}]
	${driver}
	port = ${ups_config.port}
	desc = "${ups_config.description.replace('"', r'\"')}"
	${ups_config.options}
