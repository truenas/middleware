<%
    from middlewared.utils.auth import LEGACY_API_KEY_USERNAME
    from middlewared.utils.pam import STANDALONE_ACCOUNT, FAILLOCK_AUTH_FAIL, FAILLOCK_AUTH_SUCC

    ds_auth = render_ctx['datastore.config']['stg_ds_auth']
    truenas_admin_string = ''
    for key in render_ctx['api_key.query']:
        if key.user_identifier == LEGACY_API_KEY_USERNAME:
            truenas_admin_string = f'truenas_admin={key.username}'
            break
%>\
# Pam configuration for API key authentication

auth		[success=1 default=die]		pam_truenas.so	allow_password_auth
@include common-auth-unix
%if ds_auth:
@include common-account
%else:
${'\n'.join(line.as_conf() for line in STANDALONE_ACCOUNT.primary)}
@include common-account-unix
%if render_ctx['system.security.config']['enable_gpos_stig']:
${FAILLOCK_AUTH_SUCC.as_conf()}
%endif
%endif
password	required			pam_deny.so
@include truenas-session
