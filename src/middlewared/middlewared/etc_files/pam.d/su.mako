#
# $FreeBSD: head/etc/pam.d/su 219663 2011-03-15 10:13:35Z des $
#
# PAM configuration for the "su" service
#
<%namespace name="pam" file="pam.inc.mako" />
<%
    dsp = pam.getDirectoryServicePam(middleware=middleware, file='su')
%>
# auth
auth		sufficient	pam_rootok.so		no_warn
auth		sufficient	pam_self.so		no_warn
% if dsp.enabled() and dsp.name() != 'NIS':
${dsp.pam_auth()}
% endif
#auth		sufficient	pam_krb5.so		no_warn try_first_pass
auth		requisite	pam_group.so		no_warn group=wheel root_only ruser
auth		include		system

# account
account		include		system

# session
session		required	pam_permit.so
% if dsp.enabled():
${dsp.pam_session()}
% endif
