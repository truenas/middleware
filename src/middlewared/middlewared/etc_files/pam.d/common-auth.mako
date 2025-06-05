#
# /etc/pam.d/common-auth - authentication settings common to all services
#
# This file is included from other service-specific PAM config files,
# and should contain a list of the authentication modules that define
# the central authentication scheme for use on the system
# (e.g., /etc/shadow, LDAP, Kerberos, etc.).  The default is to use the
# traditional Unix authentication mechanisms.

<%
    from middlewared.utils.directoryservices.constants import DSType
    from middlewared.utils.pam import (
        STANDALONE_AUTH, AD_AUTH, SSS_AUTH,
        FAILLOCK_AUTH_FAIL, FAILLOCK_AUTH_SUCC,
    )

    match (dstype := render_ctx['directoryservices.status']['type']):
        # dstype of None means standalone server
        case None:
            conf = STANDALONE_AUTH
        case DSType.AD.value:
            conf = AD_AUTH
        case DSType.LDAP.value | DSType.IPA.value:
            conf = SSS_AUTH
        case _:
            raise TypeError(f'{dstype}: unknown DSType')
%>\

% if render_ctx['system.security.config']['enable_gpos_stig']:
auth	optional	pam_faildelay.so	delay=4000000
% endif
% if conf.primary:
${'\n'.join(line.as_conf() for line in conf.primary)}
% endif
@include common-auth-unix
% if render_ctx['system.security.config']['enable_gpos_stig']:
${FAILLOCK_AUTH_SUCC.as_conf()}
% endif
% if conf.secondary:
${'\n'.join(line.as_conf() for line in conf.secondary)}
% endif
