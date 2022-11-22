<%
    ds_auth = middleware.call_sync('datastore.config', 'system.settings')['stg_ds_auth']
%>\
# PAM configuration for the middleware (Web UI login)

%if ds_auth:
@include common-auth
%else:
@include common-auth-unix
%endif

account	required	pam_deny.so
password	required	pam_deny.so
session	required	pam_deny.so
