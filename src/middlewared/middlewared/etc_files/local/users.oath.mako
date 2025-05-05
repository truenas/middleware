<%
        users = []
        if render_ctx['auth.twofactor.config']['enabled']:
	    users = middleware.call_sync('auth.twofactor.get_users_config')
%>\
% for user in users:
${f'HOTP/T{user["interval"]}/{user["otp_digits"]}'}	${user['username']}	-	${user['secret_hex']}
% endfor
