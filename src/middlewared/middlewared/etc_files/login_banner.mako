<%
	login_banner = render_ctx['system.advanced.login_banner']
	if login_banner == '':
		raise FileShouldNotExist()
%>\
${login_banner}
