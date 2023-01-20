#
# /etc/pam.d/common-session-noninteractive - session-related modules
# common to all non-interactive services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of modules that define tasks to be performed
# at the start and end of all non-interactive sessions.
#
<%namespace name="pam" file="pam.inc.mako" />\
<%
        dsp = pam.getDirectoryServicePam(middleware=middleware, render_ctx=render_ctx).pam_session()
%>\

${'\n'.join(dsp['primary'])}
session	[default=1]			pam_permit.so
session	requisite			pam_deny.so
session	required			pam_permit.so
${'\n'.join(dsp['additional'])}
