#
# /etc/pam.d/common-account - authorization settings common to all services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of the authorization modules that define
# the central access policy for use on the system.  The default is to
# only deny service to users whose accounts are expired in /etc/shadow.
#
<%
    from middlewared.utils.directoryservices.constants import DSType
    from middlewared.utils.pam import STANDALONE_ACCOUNT, AD_ACCOUNT, SSS_ACCOUNT

    match (dstype := render_ctx['directoryservices.status']['type']):
        # dstype of None means standalone server
        case None:
            conf = STANDALONE_ACCOUNT
        case DSType.AD.value:
            conf = AD_ACCOUNT
        case DSType.LDAP.value | DSType.IPA.value:
            conf = SSS_ACCOUNT
        case _:
            raise TypeError(f'{dstype}: unknown DSType')
%>\

% if conf.primary:
${'\n'.join(line.as_conf() for line in conf.primary)}
% endif
account	requisite			pam_deny.so
account	required			pam_permit.so
% if conf.secondary:
${'\n'.join(line.as_conf() for line in conf.secondary)}
% endif
