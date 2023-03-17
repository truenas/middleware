<%
	import base64

	twofactor_auth = render_ctx['auth.twofactor.config']
	users = middleware.call_sync(
	    'auth.twofactor.get_users_twofactor_configuration'
	) if twofactor_auth['enabled'] and twofactor_auth['services']['ssh'] else []
	if not users:
		raise FileShouldNotExist()
%>\
% for user in users:
${f'HOTP/T{twofactor_auth["interval"]}/{twofactor_auth["otp_digits"]}'}	${user['username']}	-	${user['secret_hex']}
% endfor
