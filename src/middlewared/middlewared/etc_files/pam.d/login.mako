#
# $FreeBSD: head/etc/pam.d/login 170510 2007-06-10 18:57:20Z yar $
#
# PAM configuration for the "login" service
#
<%namespace name="pam" file="pam.inc.mako" />
<%
        dsp = pam.getDirectoryServicePam(middleware=middleware, file='login')
%>
# auth
auth		sufficient	pam_self.so		no_warn
% if dsp.enabled() and dsp.name() != 'NIS':
${dsp.pam_auth()}
% endif
auth		include		system

# account
account		requisite	pam_securetty.so
account		required	pam_nologin.so
% if dsp.enabled() and dsp.name() != 'NIS':
${dsp.pam_account()}
% endif
account		include		system

# session
session		include		system

# password
password	include		system
