#
# $FreeBSD: src/etc/pam.d/sudo,v 1.18 2009/10/05 09:28:54 des Exp $
#
# PAM configuration for the "sudo" service
#
<%namespace name="pam" file="pam.inc.mako" />
<%
    dsp = pam.getDirectoryServicePam(middleware=middleware, file='sudo')
%>
# auth
auth		sufficient	pam_opie.so		no_warn no_fake_prompts
auth		requisite	pam_opieaccess.so	no_warn allow_local
% if dsp.enabled() and dsp.name() == 'LDAP':
${dsp.pam_auth()}
% endif
auth		required	pam_unix.so		no_warn try_first_pass

# account
account		required	pam_nologin.so
account		required	pam_login_access.so
% if dsp.enabled() and dsp.name() == 'LDAP':
${dsp.pam_account()}
% endif
account		required	pam_unix.so

# session
session		required	pam_permit.so

# password
% if dsp.enabled() and dsp.name() == 'LDAP':
${dsp.pam_password()}
% endif
password	required	pam_unix.so		no_warn try_first_pass
