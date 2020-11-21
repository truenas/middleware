<%
	try:
		middleware.call_sync('openvpn.client.config_valid')
	except Exception as e:
		raise FileShouldNotExist()

	config = middleware.call_sync('openvpn.client.config')
	root_ca = middleware.call_sync('certificateauthority.query', [['id', '=', config['root_ca']]], {'get': True})
	client_cert = middleware.call_sync('certificate.query', [['id', '=', config['client_certificate']]], {'get': True})
%>\
client
% if IS_LINUX:
dev ${config['interface']}
dev-type ${config['device_type'].lower()}
% else:
dev ${config['device_type'].lower()}
#dev-type ${config['device_type'].lower()} -FIXME: This does not work, it is an openvpn issue in FreeBSD
% endif
proto ${config['protocol'].lower()}
port ${config['port']}
remote ${config['remote']}
user nobody
group ${"nobody" if IS_FREEBSD else "nogroup"}
persist-key
persist-tun
ca ${root_ca['certificate_path']}
cert ${client_cert['certificate_path']}
key ${client_cert['privatekey_path']}
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
