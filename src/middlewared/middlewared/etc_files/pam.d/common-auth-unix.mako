<%
    from middlewared.utils.pam import FAILLOCK_AUTH_FAIL
%>

% if render_ctx['system.security.config']['enable_gpos_stig']:
${FAILLOCK_AUTH_FAIL.as_conf()}
% else:
auth	requisite			pam_deny.so
% endif
auth	required			pam_permit.so
