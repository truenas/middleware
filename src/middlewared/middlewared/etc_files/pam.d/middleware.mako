<%
    from middlewared.utils.pam import STANDALONE_AUTH

    ds_auth = render_ctx['datastore.config']['stg_ds_auth']
%>\
# PAM configuration for the middleware (Web UI / API login)

%if ds_auth:
@include common-auth
%else:
${'\n'.join(line.as_conf() for line in STANDALONE_AUTH.primary)}
@include common-auth-unix
%endif
@include common-account
password	required	pam_deny.so
session	required	pam_deny.so
