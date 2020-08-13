<%
	config = middleware.call_sync('datastore.config', 'system.truecommand')
	if not config['enabled'] or config['api_key_state'] != 'CONNECTED' or any(
		not config[k] for k in ('wg_address', 'wg_private_key', 'remote_address', 'endpoint', 'tc_public_key')
	):
		raise FileShouldNotExist()
%>\
[Interface]
Address = ${config['wg_address']}
PrivateKey = ${config['wg_private_key']}

[Peer]
PublicKey = ${config['tc_public_key']}
Endpoint = ${config['endpoint']}
AllowedIPs = ${config['remote_address']}

PersistentKeepalive = 25
