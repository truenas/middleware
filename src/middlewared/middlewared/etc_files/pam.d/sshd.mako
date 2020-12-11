#
# $FreeBSD: head/etc/pam.d/sshd 197769 2009-10-05 09:28:54Z des $
#
# PAM configuration for the "sshd" service
#
<%namespace name="pam" file="pam.inc.mako" />\
<%
	dsp = pam.getDirectoryServicePam(middleware=middleware, file='sshd')
	twofactor_auth = middleware.call_sync('auth.twofactor.config')
	twofactor_enabled = twofactor_auth['enabled'] and twofactor_auth['services']['ssh']
%>\
# auth
auth		sufficient	pam_opie.so		no_warn no_fake_prompts
auth		requisite	pam_opieaccess.so	no_warn allow_local
% if dsp.enabled() and dsp.name() != 'NIS' and not twofactor_enabled:
${dsp.pam_auth()}
% endif
#auth		sufficient	pam_ssh.so		no_warn try_first_pass
auth		required	pam_unix.so		no_warn try_first_pass
% if twofactor_enabled:
auth		required	/usr/local/lib/security/pam_oath.so	usersfile=/usr/local/etc/users.oath	window=${twofactor_auth['window']}
% endif

# account
account		required	pam_nologin.so
account		required	pam_login_access.so
% if dsp.enabled() and dsp.name() != 'NIS' and not twofactor_enabled:
${dsp.pam_account()}
% endif
account		required	pam_unix.so

# session
#session	optional	pam_ssh.so		want_agent
session		required	pam_permit.so
% if dsp.enabled() and not twofactor_enabled:
${dsp.pam_session()}
% endif

# password
% if dsp.enabled() and dsp.name() != 'NIS' and not twofactor_enabled:
${dsp.pam_password()}
% endif
password	required	pam_unix.so		no_warn try_first_pass
