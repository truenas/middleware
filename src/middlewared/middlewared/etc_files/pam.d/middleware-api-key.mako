<%
    from middlewared.utils import filter_list
    from middlewared.utils.auth import LEGACY_API_KEY_USERNAME

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
<%namespace name="pam" file="pam.inc.mako" />\
<%
        dsp = pam.getNoDirectoryServicePam().pam_account()
%>\
${'\n'.join(dsp['primary'])}
@include common-account-unix
%endif
password	required			pam_deny.so
session		required			pam_deny.so
