<%
    ds_auth = middleware.call_sync('datastore.config', 'system.settings')['stg_ds_auth']
%>\
# PAM configuration for the middleware (Web UI login)

%if ds_auth:
@include common-auth
@include common-account
@include common-session
@include common-session
@include common-password
%else:
@include common-auth-unix
@include common-account-unix
@include common-session-unix-header
@include common-session-unix-footer
@include common-password-unix
%endif
