<%
    from middlewared.utils.filter_list import filter_list
    from middlewared.utils.auth import LEGACY_API_KEY_USERNAME
    from middlewared.utils.pam import STANDALONE_ACCOUNT, FAILLOCK_AUTH_FAIL, FAILLOCK_AUTH_SUCC

    ds_auth = render_ctx['datastore.config']['stg_ds_auth']
    truenas_admin_string = ''
    legacy_users = filter_list(render_ctx['api_key.query'], [
        ['user_identifier', '=', LEGACY_API_KEY_USERNAME]
    ], {'select': ['username']})

    if legacy_users:
        truenas_admin_string = f'truenas_admin={legacy_users[0]["username"]}'
%>\
# Pam configuration for API key authentication

auth		[success=1 default=die]		pam_tdb.so ${truenas_admin_string}
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
@include middleware-session
