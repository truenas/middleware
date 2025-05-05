#
# /etc/pam.d/common-session-noninteractive - session-related modules
# common to all non-interactive services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of modules that define tasks to be performed
# at the start and end of all non-interactive sessions.
#
<%
    from middlewared.utils.directoryservices.constants import DSType
    from middlewared.utils.pam import PAMModule, STANDALONE_SESSION, AD_SESSION, SSS_SESSION

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
%>\

% if conf.primary:
${'\n'.join(line.as_conf() for line in conf.primary)}
% endif
session	[default=1]			pam_permit.so
session	requisite			pam_deny.so
session	required			pam_permit.so
% if conf.secondary:
${'\n'.join(line.as_conf() for line in conf.secondary if line.pam_module is not PAMModule.MKHOMEDIR)}
% endif
