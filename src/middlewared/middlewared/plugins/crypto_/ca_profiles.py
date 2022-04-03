from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service

from .utils import DEFAULT_LIFETIME_DAYS


class CertificateAuthorityService(Service):

    class Config:
        cli_namespace = 'system.certificate.authority'

    PROFILES = {
        'Openvpn Root CA': {
            'cert_extensions': {
                'AuthorityKeyIdentifier': {
                    'enabled': True,
                    'authority_cert_issuer': True,
                    'extension_critical': False
                },
                'KeyUsage': {
                    'enabled': True,
                    'key_cert_sign': True,
                    'crl_sign': True,
                    'extension_critical': True
                },
                'BasicConstraints': {
                    'enabled': True,
                    'ca': True,
                    'extension_critical': True
                },
                'ExtendedKeyUsage': {
                    'enabled': True,
                    'extension_critical': False,
                    'usages': [
                        'SERVER_AUTH', 'CLIENT_AUTH',
                    ]
                }
            },
            'key_length': 2048,
            'key_type': 'RSA',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'digest_algorithm': 'SHA256'
        },
        'CA': {
            'key_length': 2048,
            'key_type': 'RSA',
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'digest_algorithm': 'SHA256',
            'cert_extensions': {
                'KeyUsage': {
                    'enabled': True,
                    'key_cert_sign': True,
                    'crl_sign': True,
                    'extension_critical': True
                },
                'BasicConstraints': {
                    'enabled': True,
                    'ca': True,
                    'extension_critical': True
                },
                'ExtendedKeyUsage': {
                    'enabled': True,
                    'extension_critical': False,
                    'usages': ['SERVER_AUTH']
                }
            }
        }
    }

    @accepts()
    @returns(Dict(
        'certificate_authority_profiles',
        *[Dict(profile, additional_attrs=True) for profile in PROFILES]
    ))
    async def profiles(self):
        """
        Returns a dictionary of predefined options for specific use cases i.e OpenVPN certificate authority
        configurations which can be used for creating certificate authorities.
        """
        return self.PROFILES
