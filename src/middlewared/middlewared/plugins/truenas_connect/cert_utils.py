from truenas_crypto_utils.csr import generate_certificate_signing_request


CERT_BOT_EMAIL = 'cert-bot@ixsystems.com'


def get_hostnames_from_hostname_config(hostname_config: dict) -> list[str]:
    return [f'*.{hostname_config["base_domain"]}']


def generate_csr(hostnames: list[str]) -> (str, str):
    return generate_certificate_signing_request({
        'key_type': 'RSA',
        'key_length': 4096,
        'san': hostnames,
        'country': 'US',
        'state': 'TN',
        'city': 'Maryville',
        'organization': 'iX',
        'organizational_unit': 'TNC',
        'email': CERT_BOT_EMAIL,
        'digest_algorithm': 'SHA256',
        'cert_extensions': {
            'BasicConstraints': {
                'enabled': True,
                'ca': False,
                'extension_critical': True,
            },
            'ExtendedKeyUsage': {
                'enabled': True,
                'extension_critical': True,
                'usages': ['SERVER_AUTH', 'CLIENT_AUTH'],
            },
            'KeyUsage': {
                'enabled': True,
                'extension_critical': True,
                'digital_signature': True,
                'key_encipherment': True,
                'key_agreement': True,
            },
        }
    })
