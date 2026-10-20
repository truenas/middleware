<%
    from middlewared.utils.pam import STANDALONE_ACCOUNT

    ds_auth = render_ctx['datastore.config']['stg_ds_auth']
%>\
# PAM configuration for the middleware sessions over unix socket

auth		sufficient	pam_access.so
%if ds_auth:
@include common-account
%else:
${'\n'.join(line.as_conf() for line in STANDALONE_ACCOUNT.primary)}
account 	requisite	pam_deny.so
account		required	pam_permit.so
%endif
password	required	pam_deny.so
@include truenas-session
