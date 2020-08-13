<%
	import base64

	twofactor_auth = middleware.call_sync('auth.twofactor.config')
	if twofactor_auth['enabled'] and twofactor_auth['services']['ssh']:
		twofactor_auth['secret_hex'] = base64.b16encode(base64.b32decode(twofactor_auth['secret'])).decode()
	else:
		raise FileShouldNotExist()
%>\
${f'HOTP/T{twofactor_auth["interval"]}/{twofactor_auth["otp_digits"]}'}	root	-	${twofactor_auth['secret_hex']}
