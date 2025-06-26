<%
    from middlewared.utils.pam import STANDALONE_AUTH, FAILLOCK_AUTH_FAIL, FAILLOCK_AUTH_SUCC

    ds_auth = render_ctx['datastore.config']['stg_ds_auth']
%>\
# PAM configuration for the middleware (Web UI / API login)

%if ds_auth:
@include common-auth
%else:
${'\n'.join(line.as_conf() for line in STANDALONE_AUTH.primary)}
@include common-auth-unix
%if render_ctx['system.security.config']['enable_gpos_stig']:
${FAILLOCK_AUTH_SUCC.as_conf()}
%endif
%endif
@include common-account
password	required	pam_deny.so
@include middleware-session
