<%
	login_banner = middleware.call_sync('system.advanced.login_banner')
	if login_banner == '':
		raise FileShouldNotExist()
%>\
${login_banner}
