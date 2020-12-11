#
# $FreeBSD: head/etc/pam.d/ftpd 197769 2009-10-05 09:28:54Z des $
#
# PAM configuration for the "ftpd" service
#
<%namespace name="pam" file="pam.inc.mako" />
<%
        dsp = pam.getDirectoryServicePam(middleware=middleware, file='ftp')
%>
# auth
auth		sufficient	pam_opie.so		no_warn no_fake_prompts
auth		requisite	pam_opieaccess.so	no_warn allow_local
% if dsp.enabled() and dsp.name() != 'NIS':
${dsp.pam_auth()}
% endif
#auth		sufficient	pam_ssh.so		no_warn try_first_pass
auth		required	pam_unix.so		no_warn try_first_pass

# account
account		required	pam_nologin.so
% if dsp.enabled() and dsp.name() != 'NIS':
${dsp.pam_account()}
% endif
account		required	pam_unix.so

# session
session		required	pam_permit.so
% if dsp.enabled():
${dsp.pam_session()}
% endif
