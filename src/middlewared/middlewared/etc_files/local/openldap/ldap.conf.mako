<%
    from middlewared.plugins.etc import FileShouldNotExist
    from middlewared.utils.directoryservices.constants import DSType

    ds_config = middleware.call_sync('directoryservices.config')
    if not ds_config['enable']:
        raise FileShouldNotExist

    uri = None
    credential = ds_config['credential']

    match ds_config['service_type']:
        case DSType.AD.value:
            idmap = ds_config['idmap']['idmap_domain']
            if idmap['idmap_backend'] not in ('LDAP', 'RFC2307'):
                raise FileShouldNotExist

            uri = idmap['ldap_url']
            basedn = idmap['ldap_base_dn']
            credential = {
                'credential_type': 'LDAP_PLAIN',
                'binddn': idmap['ldap_user_dn'],
                'bindpw': idmap['ldap_user_dn_password']
            }
        case DSType.LDAP.value:
            uri = ' '.join(ds_config['server_urls'])
            basedn = ds_config['basedn']

        case DSType.IPA.value:
            uri = f'ldaps://{ds_config["target_server"]}'
            basedn = ds_config['basedn']

        case _:
            middleware.logger.error('%s: unexpected service type', ds_config['service_type'])
            raise FileShouldNotExist


    if credential['credential_type'] == 'LDAP_MTLS':
        cert = middlware.call_sync('certificate.query', [['cert_name', '=', credential['client_certificate']]], {'get': True})
        tls_certfile = cert['certificate_path']
        tls_keyfile = cert['privatekey_path']

    if not uri:
        middleware.logger.error('Directory serivce does not have a configured LDAP URI')
        raise FileShouldNotExist
%>
URI ${uri}
BASE ${basedn}
NETWORK_TIMEOUT ${ds_config['timeout']}
TIMEOUT ${ds_config['timeout']}
TLS_CACERT /etc/ssl/certs/ca-certificates.crt
% if credential['credential_type'] == 'LDAP_MTLS':
TLS_CERT ${tls_certfile}
TLS_KEY ${tls_keyfile}
SASL_MECH EXTERNAL
% endif
TLS_REQCERT ${'demand' if tls_reqcert else 'allow'}
% if credential['credential_type'].startswith('KERBEROS'):
SASL_MECH GSSAPI
SASL_REALM ${ds_config['kerberos_realm']}
% elif credential['credential_type'] == 'LDAP_PLAIN':
BINDDN ${credential['binddn']}
% endif
