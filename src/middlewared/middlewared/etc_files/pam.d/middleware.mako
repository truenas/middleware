<%
    ds_auth = middleware.call_sync('datastore.config', 'system.settings')['stg_ds_auth']
%>\
# PAM configuration for the middleware (Web UI / API login)

%if ds_auth:
@include common-auth
%else:
<%namespace name="pam" file="pam.inc.mako" />\
<%
        dsp = pam.getNoDirectoryServicePam().pam_auth()
%>\
${'\n'.join(dsp['primary'])}
@include common-auth-unix
%endif
@include common-account
password	required	pam_deny.so
session	required	pam_deny.so
