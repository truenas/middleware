<%
	try:
		middleware.call_sync('openvpn.client.config_valid')
	except Exception as e:
		raise FileShouldNotExist()

	config = middleware.call_sync('openvpn.client.config')
	root_ca = middleware.call_sync('certificateauthority.query', [['id', '=', config['root_ca']]], {'get': True})
	if config['client_certificate']:
		client_cert = middleware.call_sync('certificate.query', [['id', '=', config['client_certificate']]], {'get': True})
	else:
		client_cert = None
%>\
client

dev ${config['interface']}
dev-type ${config['device_type'].lower()}
proto ${config['protocol'].lower()}
port ${config['port']}
remote ${config['remote']}
user nobody
group nogroup
persist-key
persist-tun
ca ${root_ca['certificate_path']}
% if client_cert:
cert ${client_cert['certificate_path']}
key ${client_cert['privatekey_path']}
% endif
verb 3
remote-cert-tls server
% if config['compression']:
compress ${config['compression'].lower()}
% endif
% if config['authentication_algorithm']:
auth ${config['authentication_algorithm']}
% endif
% if config['cipher']:
cipher ${config['cipher']}
% endif
% if config['nobind']:
nobind
% endif
% if config['tls_crypt_auth_enabled']:
<tls-crypt>
${config['tls_crypt_auth']}
</tls-crypt>
% endif
${config['additional_parameters']}
