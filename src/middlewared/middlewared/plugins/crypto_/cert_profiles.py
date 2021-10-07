import copy
import functools

from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service

from .utils import NOT_VALID_AFTER_DEFAULT


CERTIFICATE_PROFILES = {
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
        'lifetime': NOT_VALID_AFTER_DEFAULT,
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
        'lifetime': NOT_VALID_AFTER_DEFAULT,
        'digest_algorithm': 'SHA256'
    }
}


@functools.cache
def get_csr_profiles():
    profiles = copy.deepcopy(CERTIFICATE_PROFILES)
    for key, schema in filter(lambda v: 'cert_extensions' in v[1], profiles.items()):
        schema['cert_extensions'].pop('AuthorityKeyIdentifier', None)
    return profiles


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
        *[Dict(profile, additional_attrs=True) for profile in get_csr_profiles()],
        example=get_csr_profiles(),
    ))
    async def certificate_signing_requests_profiles(self):
        """
        Returns a dictionary of predefined options for specific use cases i.e openvpn client/server
        configurations which can be used for creating certificate signing requests.
        """
        return get_csr_profiles()
