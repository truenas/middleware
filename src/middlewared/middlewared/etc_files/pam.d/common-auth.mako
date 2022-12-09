#
# /etc/pam.d/common-auth - authentication settings common to all services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of the authentication modules that define
# the central authentication scheme for use on the system
# (e.g., /etc/shadow, LDAP, Kerberos, etc.).  The default is to use the
# traditional Unix authentication mechanisms.

<%namespace name="pam" file="pam.inc.mako" />\
<%
        dsp = pam.getDirectoryServicePam(middleware=middleware, render_ctx=render_ctx)
%>\

${dsp.pam_auth()}
auth	requisite			pam_deny.so
auth	required			pam_permit.so
