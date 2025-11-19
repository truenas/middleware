#
# /etc/pam.d/common-session - session-related modules common to all services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of modules that define tasks to be performed
# at the start and end of sessions of *any* kind (both interactive and
# non-interactive).

<%
    from middlewared.utils.directoryservices.constants import DSType
    from middlewared.utils.pam import (
        TTY_AUDIT_LINE, STANDALONE_SESSION, AD_SESSION, SSS_SESSION,
        TRUENAS_SESSION_LIMIT, TRUENAS_SESSION_NO_LIMIT
    )

    tty_audit_line = None

    match (dstype := render_ctx['directoryservices.status']['type']):
        # dstype of None means standalone server
        case None:
            conf = STANDALONE_SESSION
        case DSType.AD.value:
            conf = AD_SESSION
        case DSType.LDAP.value | DSType.IPA.value:
            conf = SSS_SESSION
        case _:
            raise TypeError(f'{dstype}: unknown DSType')

    if render_ctx['system.security.config']['enable_gpos_stig']:
        tty_audit_line = TTY_AUDIT_LINE
        truenas_session_line = TRUENAS_SESSION_LIMIT
    else:
        truenas_session_line = TRUENAS_SESSION_NO_LIMIT
%>\
% if tty_audit_line:
${TTY_AUDIT_LINE.as_conf()}
% endif
${truenas_session_line.as_conf()}
% if conf.primary:
${'\n'.join(line.as_conf() for line in conf.primary)}
% endif
session	[default=1]			pam_permit.so
session	requisite			pam_deny.so
session	required			pam_permit.so
session	optional			pam_systemd.so
% if conf.secondary:
${'\n'.join(line.as_conf() for line in conf.secondary)}
% endif
