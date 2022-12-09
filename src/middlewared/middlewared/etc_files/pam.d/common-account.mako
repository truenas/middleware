#
# /etc/pam.d/common-account - authorization settings common to all services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of the authorization modules that define
# the central access policy for use on the system.  The default is to
# only deny service to users whose accounts are expired in /etc/shadow.
#
<%namespace name="pam" file="pam.inc.mako" />\
<%
        dsp = pam.getDirectoryServicePam(middleware=middleware, render_ctx=render_ctx)
%>\

${dsp.pam_account()}
account	requisite			pam_deny.so
account	required			pam_permit.so
