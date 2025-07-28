<%
    import os

    from middlewared.plugins.etc import FileShouldNotExist
    from middlewared.utils.directoryservices import ldap_constants as constants
    from middlewared.utils.directoryservices import ldap_utils as utils
    from middlewared.utils.directoryservices.common import ds_config_to_fqdn
    from middlewared.utils.directoryservices.constants import DSCredType, DSType

    ds_config = middleware.call_sync('directoryservices.config')
    ds_type = ds_config['service_type']
    if ds_type == DSType.LDAP.value:
        kerberos_realm = ds_config['kerberos_realm'] 
        aux = []
        map_params = utils.attribute_maps_data_to_params(ds_config['configuration']['attribute_maps'])
        search_params = utils.search_base_data_to_params(ds_config['configuration']['search_bases'])
        min_uid = 1000
        certpath = None
        if ds_config['credential']['credential_type'] == DSCredType.LDAP_MTLS:
            try:
                cert = middleware.call_sync('certificate.query', [
                    ('cert_name', '=', ds_config['credential']['client_certificate'])
                ], {'get': True})
            except Exception:
                middleware.logger.error('Failed to retrieve client certificate', exc_info=True)
            else:
                certpath = cert['certificate_path']
                keypath = cert['privatekey_path']

        domain = kerberos_realm or 'LDAP'
        for param in (ds_config['configuration']['auxiliary_parameters'] or '').splitlines():
            param = param.strip()
            if not param.startswith('nss_min_uid'):
                aux.append(param)
            else:
                try:
                    min_uid = param.split()[1]
                except Exception:
                    pass

    elif ds_type == DSType.IPA.value:
        ipa_hostname = ds_config_to_fqdn(ds_config)

    else:
        raise FileShouldNotExist

    os.makedirs('/var/run/sssd-cache/mc', mode=0o755, exist_ok=True)
    os.makedirs('/var/run/sssd-cache/db', mode=0o755, exist_ok=True)

%>
% if ds_type == DSType.LDAP.value:
[sssd]
domains = ${domain}
services = nss, pam
config_file_version = 2

[domain/${domain}]
id_provider = ldap
auth_provider = ldap
ldap_uri = ${','.join(ds_config['configuration']['server_urls'])}
ldap_search_base = ${ds_config['configuration']['basedn']}
% if ds_config['configuration']['starttls']:
ldap_id_use_start_tls =  true
% endif
ldap_tls_cacert = /etc/ssl/certs/ca-certificates.crt
% if certpath:
ldap_tls_cert = ${certpath}
ldap_tls_key = ${keypath}
% endif
ldap_tls_reqcert = ${'demand' if ds_config['configuration']['validate_certificates'] else 'allow'}
% if ds_config['credential']['credential_type'] == DSCredType.LDAP_PLAIN:
ldap_default_bind_dn = ${ds_config['credential']['binddn']}
ldap_default_authtok = ${ds_config['credential']['bindpw']}
% endif
enumerate = ${ds_config['enable_account_cache']}
% if kerberos_realm:
ldap_sasl_mech = GSSAPI
ldap_sasl_realm = ${kerberos_realm}
% if ds_config['credential']['credential_type'] == DSCredType.KERBEROS_PRINCIPAL:
ldap_sasl_authid = ${ds_config['credential']['principal']}
% endif
% endif
timeout = ${ds_config['timeout']}
ldap_schema = ${ds_config['configuration']['schema'].lower()}
min_id = ${min_uid}
${'\n    '.join(search_params)}
${'\n    '.join(map_params)}
% if aux:
${'\n    '.join(aux)}
% endif
% elif ds_type == DSType.IPA.value:
[sssd]
domains = ${ds_config['configuration']['domain']}
services = nss, pam

[domain/${ds_config['configuration']['domain']}]
id_provider = ipa
ipa_server = _srv_, ${ds_config['configuration']['target_server']}
ipa_domain = ${ds_config['configuration']['domain']}
ipa_hostname = ${ipa_hostname.lower()}
auth_provider = ipa
access_provider = ipa
cache_credentials = True
ldap_tls_cacert = /etc/ipa/ca.crt
enumerate = ${ds_config['enable_account_cache']}
% endif
