import copy

from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service

from .utils import DEFAULT_LIFETIME_DAYS


CERTIFICATE_PROFILES = {
    # Options / EKUs reference rfc5246
    'HTTPS RSA Certificate': {
        'cert_extensions': {
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
            # Most TLS certs these days want "ClientAuth" these days.
            # LetsEncrypt appears to want this extension to issue.
            # https://community.letsencrypt.org/t/extendedkeyusage-tls-client-authentication-in-tls-server-certificates/59140/7
            'ExtendedKeyUsage': {
                'enabled': True,
                'extension_critical': True,
                'usages': [
                    'SERVER_AUTH',
                    'CLIENT_AUTH',
                ]
            },
            # RSA certs need "digitalSignature" for DHE,
            # and "keyEncipherment" for nonDHE
            # Include "keyAgreement" for compatibility (DH_DSS / DH_RSA)
            # See rfc5246
            'KeyUsage': {
                'enabled': True,
                'extension_critical': True,
                'digital_signature': True,
                'key_encipherment': True,
                'key_agreement': True,
            }
        },
        'key_length': 2048,
        'key_type': 'RSA',
        'lifetime': NOT_VALID_AFTER_DEFAULT,
        'digest_algorithm': 'SHA256'
    },
    'HTTPS ECC Certificate': {
        'cert_extensions': {
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
            # Most TLS certs these days want "ClientAuth" these days.
            # LetsEncrypt appears to want this extension to issue.
            # https://community.letsencrypt.org/t/extendedkeyusage-tls-client-authentication-in-tls-server-certificates/59140/7
            'ExtendedKeyUsage': {
                'enabled': True,
                'extension_critical': True,
                'usages': [
                    'SERVER_AUTH',
                    'CLIENT_AUTH',
                ]
            },
            # keyAgreement is not generally required for EC certs. See Google, cloudflare certs
            'KeyUsage': {
                'enabled': True,
                'extension_critical': True,
                'digital_signature': True,
            }
        },
        'ec_curve': 'SECP384R1',
        'key_type': 'EC',
        'lifetime': NOT_VALID_AFTER_DEFAULT,
        'digest_algorithm': 'SHA256'
    },
    'Openvpn Server Certificate': {
        'cert_extensions': {
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
                    'SERVER_AUTH',
                ]
            },
            'KeyUsage': {
                'enabled': True,
                'extension_critical': True,
                'digital_signature': True,
                'key_encipherment': True
            }
        },
        'key_length': 2048,
        'key_type': 'RSA',
        'lifetime': DEFAULT_LIFETIME_DAYS,
        'digest_algorithm': 'SHA256'
    },
    'Openvpn Client Certificate': {
        'cert_extensions': {
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
        },
        'key_length': 2048,
        'key_type': 'RSA',
        'lifetime': DEFAULT_LIFETIME_DAYS,
        'digest_algorithm': 'SHA256'
    }
}
CSR_PROFILES = copy.deepcopy(CERTIFICATE_PROFILES)
for key, schema in filter(lambda v: 'cert_extensions' in v[1], CSR_PROFILES.items()):
    schema['cert_extensions'].pop('AuthorityKeyIdentifier', None)


class CertificateService(Service):

    @accepts()
    @returns(Dict(
        'certificate_profiles',
        *[Dict(profile, additional_attrs=True) for profile in CERTIFICATE_PROFILES]
    ))
    async def profiles(self):
        """
        Returns a dictionary of predefined options for specific use cases i.e openvpn client/server
        configurations which can be used for creating certificates.
        """
        return CERTIFICATE_PROFILES

    @accepts()
    @returns(Dict(
        *[Dict(profile, additional_attrs=True) for profile in CSR_PROFILES],
        example=CSR_PROFILES,
    ))
    async def certificate_signing_requests_profiles(self):
        """
        Returns a dictionary of predefined options for specific use cases i.e openvpn client/server
        configurations which can be used for creating certificate signing requests.
        """
        return CSR_PROFILES
