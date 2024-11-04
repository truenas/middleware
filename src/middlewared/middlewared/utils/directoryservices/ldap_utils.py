from middlewared.utils.directoryservices.constants import (
    DSLdapSsl, DSType, DSCredentialType
)
from urllib.parse import urlparse


def hostnames_to_uris(hostname_list: list, use_ldaps: bool) -> list:
    scheme = 'ldaps' if use_ldaps else 'ldap'
    out = []

    for host in set(hostname_list):
        parsed = urlparse(f'{scheme}://{host}')
        try:
            port = parsed.port
            host = parsed.hostname
        except ValueError:
            port = None

        if port is None:
            port = 636 if use_ldaps else 389

        out.append(f'{scheme}://{host}:{port}')

    return out


def ds_config_to_ldap_client_config(config_in: dict) -> dict:
    if not config_in['enable'] or config_in['dstype'] not in (DSType.LDAP, DSType.IPA):
        raise ValueError('LDAP or IPA directory service is not enabled')

    dsconfig = config_in['configuration']
    match dsconfig['ssl_config']['ssl']:
        case DSLdapSsl.OFF:
            ssl = 'OFF'
        case DSLdapSsl.LDAPS:
            ssl = 'ON'
        case DSLdapSsl.STARTTLS:
            ssl = 'START_TLS'
        case _:
            raise ValueError(f'{dsconfig["ssl_config"]["SSL"]}: unknown SSL type')

    match config_in['dstype']:
        case DSType.LDAP:
            uri_list = hostnames_to_uris(dsconfig['server_hostnames'], ssl == 'ON')
        case DSType.IPA:
            # we're going to use GSSAPI bind for this
            assert dsconfig['kerberos_realm'] is not None, 'Kerberos realm required'
            uri_list = hostnames_to_uris([dsconfig['target_server']], False)
            ssl = 'OFF'
        case _:
            raise ValueError(f'{config_in["dstype"]}: unknown DSType')

    client_config = {
        'uri_list': uri_list,
        'basedn': dsconfig['basedn'],
        'credentials': {'binddn': '', 'bindpw': ''},
        'security': {
            'ssl': ssl,
            'sasl': 'SEAL',
            'client_certificate': '',
            'validate_certificates': dsconfig['ssl_config']['validate_certificates']
        },
        'options': {
            'timeout': config_in['timeout']['service'],
            'dns_timeout': config_in['timeout']['dns']
        }
    }

    match dsconfig['credential']['credential_type']:
        case DSCredentialType.KERBEROS_PRINCIPAL:
            client_config['bind_type'] = 'GSSAPI'
        case DSCredentialType.LDAPDN_PASSWORD:
            if dsconfig['kerberos_realm']:
                client_config['bind_type'] = 'GSSAPI'
            else:
                client_config['bind_type'] = 'PLAIN'
                client_config['credentials'] = {
                    'binddn': dsconfig['credential']['binddn'],
                    'bindpw': dsconfig['credential']['bindpw']
                }
        case DSCredentialType.CERTIFICATE:
            client_config['bind_type'] = 'EXTERNAL'
            client_config['cert_name'] = dsconfig['credential']['client_certificate']
            client_config['cert_name'] = dsconfig['credential']['client_certificate_id']
        case _:
            raise ValueError(f'{dsconfig["credential"]["credential_type"]}: unexpected cred type')

    return client_config
