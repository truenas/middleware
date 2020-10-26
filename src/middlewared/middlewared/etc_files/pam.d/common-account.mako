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
        dsp = pam.getDirectoryServicePam(middleware=middleware, file='sshd')
%>\

% if dsp.enabled() and dsp.name() != 'NIS':
${dsp.pam_account()}
% endif
# here's the fallback if no module succeeds
# here are the per-package modules (the "Primary" block)
account	[success=1 new_authtok_reqd=done default=ignore]	pam_unix.so
# here's the fallback if no module succeeds
account	requisite			pam_deny.so
# prime the stack with a positive return value if there isn't one already;
# this avoids us returning an error just because nothing sets a success code
# since the modules above will each just jump around
account	required			pam_permit.so
# and here are more per-package modules (the "Additional" block)
# end of pam-auth-update config
