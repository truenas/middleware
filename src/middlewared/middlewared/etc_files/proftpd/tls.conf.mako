<%
    ftp = render_ctx['ftp.config']
    cert = None
    tls_options = []
    if ftp['tls']:
        try:
            middleware.call_sync('certificate.cert_services_validation', ftp['ssltls_certificate'], 'ftp.ftp_ssltls_certificate_id')
        except Exception:
            # certificate is not valid
            pass
        else:
            cert = middleware.call_sync('certificate.query', [['id', '=', ftp['ssltls_certificate']]], {'get': True})

            # Generate TLS options
            for k, v in [
                ('allow_client_renegotiations', 'AllowClientRenegotiations'),
                ('allow_dot_login', 'AllowDotLogin'),
                ('allow_per_user', 'AllowPerUser'),
                ('common_name_required', 'CommonNameRequired'),
                ('enable_diags', 'EnableDiags'),
                ('export_cert_data', 'ExportCertData'),
                ('no_empty_fragments', 'NoEmptyFragments'),
                ('no_session_reuse_required', 'NoSessionReuseRequired'),
                ('stdenvvars', 'StdEnvVars'),
                ('dns_name_required', 'dNSNameRequired'),
                ('ip_address_required', 'iPAddressRequired'),
            ]:
                if ftp[f'tls_opt_{k}']:
                    tls_options.append(v)
%>
#
# Proftpd configuration for FTPS connections
#
% if cert is not None:
LoadModule mod_tls.c
<IfModule mod_tls.c>
TLSEngine on
TLSProtocol TLSv1.2 TLSv1.3
% if tls_options:
TLSOptions ${' '.join(tls_options)}
% endif
% if cert['key_type'] == 'EC':
TLSECCertificateFile "${cert['certificate_path']}"
TLSECCertificateKeyFile "${cert['privatekey_path']}"
% else:
TLSRSACertificateFile "${cert['certificate_path']}"
TLSRSACertificateKeyFile "${cert['privatekey_path']}"
% endif
% if cert['chain']:
TLSCertificateChainFile "${cert['certificate_path']}"
% endif
TLSVerifyClient off
TLSRequired ${ftp['tls_policy']}
</IfModule>
% endif
