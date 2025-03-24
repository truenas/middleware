<%
    from middlewared.plugins.etc import FileShouldNotExist
    from middlewared.plugins.ldap_ import constants, utils
    from middlewared.utils.directoryservices.constants import DSType

    ds_type = middleware.call_sync('directoryservices.status')['type']
    if ds_type == DSType.LDAP.value:
        ldap = middleware.call_sync('ldap.config')
        kerberos_realm = None
        aux = []
        map_params = utils.attribute_maps_data_to_params(ldap[constants.LDAP_ATTRIBUTE_MAP_SCHEMA_NAME])
        search_params = utils.search_base_data_to_params(ldap[constants.LDAP_SEARCH_BASES_SCHEMA_NAME])
        min_uid = 1000
        kerberos_realm = None
        certpath = None
        if ldap['certificate']:
            try:
                cert = middleware.call_sync('certificate.query', [('id', '=', ldap['certificate'])], {'get': True})
            except IndexError:
                pass
            else:
                certpath = cert['certificate_path']
                keypath = cert['privatekey_path']
        if ldap['kerberos_realm']:
            kerberos_realm = middleware.call_sync(
                'kerberos.realm.query',
                [('id', '=', ldap['kerberos_realm'])],
                {'get': True}
            )['realm']

        ldap_enabled = ldap['enable']
        domain = kerberos_realm or ldap['hostname'][0]

        ldap_enabled = ldap['enable']
        for param in ldap['auxiliary_parameters'].splitlines():
            param = param.strip()
            if not param.startswith('nss_min_uid'):
                aux.append(param)
            else:
                try:
                    min_uid = param.split()[1]
                except Exception:
                    pass

    elif ds_type == DSType.IPA.value:
        ldap = middleware.call_sync('ldap.config')
        try:
            ipa_info = middleware.call_sync('ldap.ipa_config')
        except Exception:
            middleware.logger.debug("Failed to retrieve IPA config", exc_info=True)
            raise FileShouldNotExist
    else:
        raise FileShouldNotExist

%>
% if ds_type == DSType.LDAP.value:
[sssd]
domains = ${domain}
services = nss, pam
config_file_version = 2

[domain/${domain}]
id_provider = ldap
auth_provider = ldap
ldap_uri = ${','.join(ldap['uri_list'])}
ldap_search_base = ${ldap['basedn']}
% if ldap['ssl'] == 'START_TLS':
ldap_id_use_start_tls =  true
% endif
ldap_tls_cacert = /etc/ssl/certs/ca-certificates.crt
% if certpath:
ldap_tls_cert = ${certpath}
ldap_tls_key = ${keypath}
% endif
ldap_tls_reqcert = ${'demand' if ldap['validate_certificates'] else 'allow'}
% if ldap['binddn'] and ldap['bindpw']:
ldap_default_bind_dn = ${ldap['binddn']}
ldap_default_authtok = ${ldap['bindpw']}
% endif
enumerate = ${not ldap['disable_freenas_cache']}
% if kerberos_realm:
ldap_sasl_mech = GSSAPI
ldap_sasl_realm = ${kerberos_realm}
  % if ldap['kerberos_principal']:
ldap_sasl_authid = ${ldap['kerberos_principal']}
  % endif
% endif
timeout = ${ldap['timeout']}
ldap_schema = ${ldap['schema'].lower()}
min_id = ${min_uid}
${'\n    '.join(search_params)}
${'\n    '.join(map_params)}
% if aux:
${'\n    '.join(aux)}
% endif
% elif ds_type == DSType.IPA.value:
[sssd]
domains = ${ipa_info['domain']}
services = nss, pam

[domain/${ipa_info['domain']}]
id_provider = ipa
ipa_server = _srv_, ${ipa_info['target_server']}
ipa_domain = ${ipa_info['realm'].lower()}
ipa_hostname = ${ipa_info['host'].lower()}
auth_provider = ipa
access_provider = ipa
cache_credentials = True
ldap_tls_cacert = /etc/ipa/ca.crt
enumerate = ${not ldap['disable_freenas_cache']}
% endif
