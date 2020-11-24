<%
	try:
		middleware.call_sync('openvpn.server.config_valid')
	except Exception as e:
		raise FileShouldNotExist()

	import os
	import ipaddress

	os.makedirs('/var/log/openvpn', exist_ok=True)
	config = middleware.call_sync('openvpn.server.config')
	ip = ipaddress.IPv4Network if ipaddress.ip_address(config['server']).version == 4 else ipaddress.IPv6Network
	root_ca = middleware.call_sync('certificateauthority.query', [['id', '=', config['root_ca']]], {'get': True})
	server_cert = middleware.call_sync('certificate.query', [['id', '=', config['server_certificate']]], {'get': True})
%>\
proto ${config['protocol'].lower()}
port ${config['port']}
% if IS_LINUX:
dev ${config['interface']}
dev-type ${config['device_type'].lower()}
% else:
dev ${config['device_type'].lower()}
#dev-type ${config['device_type'].lower()} -FIXME: This does not work, it is an openvpn issue in FreeBSD
% endif
ca ${root_ca['certificate_path']}
cert ${server_cert['certificate_path']}
key ${server_cert['privatekey_path']}
dh ${middleware.call_sync('certificate.dhparam')}
crl-verify ${root_ca['crl_path']}
server ${config['server']} ${ip(f'{config["server"]}/{config["netmask"]}', strict=False).netmask}
user nobody
group ${"nobody" if IS_FREEBSD else "nogroup"}
status /var/log/openvpn/openvpn-status.log
log-append  /var/log/openvpn/openvpn.log
verb 3
persist-tun
persist-key
remote-cert-tls client
% if config['topology']:
topology ${config['topology'].lower()}
% endif
% if config['cipher']:
cipher ${config['cipher']}
% endif
% if config['compression']:
compress ${config['compression'].lower()}
% endif
% if config['authentication_algorithm']:
auth ${config['authentication_algorithm']}
% endif
% if config['tls_crypt_auth_enabled']:
<tls-crypt>
${config['tls_crypt_auth']}
</tls-crypt>
% endif
${config['additional_parameters']}
