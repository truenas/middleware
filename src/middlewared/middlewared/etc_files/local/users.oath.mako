<%
	import base64

	twofactor_auth = render_ctx['auth.twofactor.config']
	users = middleware.call_sync(
	    'auth.twofactor.get_users_config'
	) if twofactor_auth['enabled'] else []
%>\
% for user in users:
${f'HOTP/T{user["interval"]}/{user["otp_digits"]}'}	${user['username']}	-	${user['secret_hex']}
% endfor
