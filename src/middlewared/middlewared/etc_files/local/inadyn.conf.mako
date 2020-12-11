<%
	import re

	config = middleware.call_sync('dyndns.config')
%>\
% if config['period']:
period = ${config['period']}
% endif
% if not config['provider']:
<% return STOP_RENDERING %>
% endif
% if config['provider'] == 'custom':
custom customProvider {
    ddns-server = "${config['custom_ddns_server']}"
    ddns-path = "${config['custom_ddns_path']}"
% else:
provider ${config['provider']} {
% endif
% if config['ssl']:
    ssl = true
% else:
    ssl = false
% endif
% if config['checkip_server'] and config['checkip_path']:
	% if config['checkip_ssl']:
    checkip-ssl = true
	% else:
    checkip-ssl = false
	% endif
    checkip-server = "${config['checkip_server']}"
    checkip-path = "${config['checkip_path']}"
% endif
% if config['username']:
    username = "${config['username']}"
% endif
% if config['password']:
    password = '${re.sub(r"(\\|')", r"\\\1", config['password'])}'
% endif
    hostname = { ${', '.join(map(lambda d: f'"{d}"', config['domain']))} }
}
