import contextlib
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.crypto import root_certificate_authority, get_cert_params


@contextlib.contextmanager
def openvpn_server_update(server_cert_name, root_ca_id):
    with generate_server_certificate(server_cert_name, root_ca_id) as server_cert:
        call('openvpn.server.update', {
            'port': 1199,
            'protocol': 'UDP',
            'device_type': 'TUN',
            'server': '192.168.0.10',
            'netmask': 24,
            'server_certificate': server_cert['id'],
            'root_ca': root_ca_id,
            'tls_crypt_auth_enabled': False,
        })
        server_config = call('openvpn.server.config')
        try:
            yield server_config
        finally:
            call('datastore.update', 'services.openvpnserver', server_config['id'],
                 {'root_ca': None, 'server_certificate': None})


SERVER_CERT_EXT = {
    'BasicConstraints': {
        'enabled': True,
        'extension_critical': True
    },
    'AuthorityKeyIdentifier': {
        'enabled': True,
        'authority_cert_issuer': True
    },
    'ExtendedKeyUsage': {
        'enabled': True,
        'usages': [
            'SERVER_AUTH'
        ],
        'extension_critical': True
    },
    'KeyUsage': {
        'enabled': True,
        'extension_critical': True,
        'digital_signature': True,
        'key_encipherment': True,
    }
}


@contextlib.contextmanager
def generate_server_certificate(server_cert_name, root_ca_id):
    cert_params = get_cert_params()
    cert_params['key_length'] = 2048
    cert_params['cert_extensions'] = SERVER_CERT_EXT
    cert_params.pop('serial')

    call('certificate.create', {
        'name': server_cert_name,
        'create_type': 'CERTIFICATE_CREATE_INTERNAL',
        'signedby': root_ca_id,
        **cert_params,
    }, job=True)
    server_cert = call('certificate.query', [['name', '=', server_cert_name]], {'get': True})

    try:
        yield server_cert
    finally:
        call('certificate.delete', server_cert['id'], job=True)


CLIENT_CERT_EXT = {
    'BasicConstraints': {
        'enabled': True,
        'ca': False,
        'extension_critical': True
    },
    'AuthorityKeyIdentifier': {
        'enabled': True,
        'authority_cert_issuer': True,
        'extension_critical': False
    },
    'ExtendedKeyUsage': {
        'enabled': True,
        'extension_critical': True,
        'usages': [
            'CLIENT_AUTH',
        ]
    },
    'KeyUsage': {
        'enabled': True,
        'extension_critical': True,
        'digital_signature': True,
        'key_agreement': True,
    }
}


@contextlib.contextmanager
def generate_client_certificate(client_cert_name, root_ca_id):
    cert_params = get_cert_params()
    cert_params['cert_extensions'] = CLIENT_CERT_EXT
    cert_params['key_length'] = 2048
    cert_params.pop('serial')

    call('certificate.create', {
        'name': client_cert_name,
        'create_type': 'CERTIFICATE_CREATE_INTERNAL',
        'signedby': root_ca_id,
        **cert_params
    }, job=True)
    client_cert = call('certificate.query', [['name', '=', client_cert_name]], {'get': True})
    try:
        yield client_cert
    finally:
        call('certificate.delete', client_cert['id'], job=True)


def test_client_configuration_generate():
    with root_certificate_authority('root-ca') as root_ca:
        with generate_client_certificate('client-cert', root_ca['id']) as client_cert:
            with openvpn_server_update('server-cert', root_ca['id']):
                assert call('openvpn.server.client_configuration_generation', client_cert['id'],
                            '192.168.0.101') is not None
