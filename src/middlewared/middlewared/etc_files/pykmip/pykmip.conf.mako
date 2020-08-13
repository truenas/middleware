<%
	kmip_config = middleware.call_sync('kmip.config')
	cert = middleware.call_sync('certificate.query', [['id', '=', kmip_config['certificate']]])
	ca = middleware.call_sync('certificateauthority.query', [['id', '=', kmip_config['certificate_authority']]])
%>\
[client]
host=${kmip_config['server']}
port=${kmip_config['port']}
% if cert and ca:
certfile=${cert[0]['certificate_path']}
keyfile=${cert[0]['privatekey_path']}
ca_certs=${ca[0]['certificate_path']}
% endif
cert_reqs=CERT_REQUIRED
