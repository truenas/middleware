<%
    from middlewared.utils.pam import PAMModule, STANDALONE_SESSION

    ds_auth = render_ctx['datastore.config']['stg_ds_auth']
%>\
# PAM configuration for the middleware (Web UI / API login)

%if ds_auth:
@include common-session-noninteractive
%else:
session [default=1]			pam_permit.so
session	requisite			pam_deny.so
session	required			pam_permit.so
${'\n'.join(line.as_conf() for line in STANDALONE_SESSION.secondary if line.pam_module is not PAMModule.MKHOMEDIR)}
%endif
%if render_ctx['system.security.config']['enable_gpos_stig']:
session	required			pam_limits.so
%endif
