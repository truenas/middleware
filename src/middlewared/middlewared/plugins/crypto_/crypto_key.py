from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, Str
from middlewared.service import Service
from middlewared.validators import Email

from .generate_ca import generate_certificate_authority
from .generate_certs import generate_certificate
from .generate_self_signed import generate_self_signed_certificate
from .generate_utils import normalize_san, sign_csr_with_ca
from .utils import EKU_OIDS


class CryptoKeyService(Service):

    class Config:
        private = True

    def normalize_san(self, san_list):
        return normalize_san(san_list)

    def generate_self_signed_certificate(self):
        return generate_self_signed_certificate()

    @accepts(
        Dict(
            'certificate_cert_info',
            Int('key_length'),
            Int('serial', required=False, null=True),
            Int('lifetime', required=True),
            Str('ca_certificate', required=False, max_length=None),
            Str('ca_privatekey', required=False, max_length=None),
            Str('key_type', required=False),
            Str('ec_curve', required=False),
            Str('country', required=True),
            Str('state', required=True),
            Str('city', required=True),
            Str('organization', required=True),
            Str('organizational_unit'),
            Str('common', null=True),
            Str('email', validators=[Email()], required=True),
            Str('digest_algorithm', enum=['SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512']),
            List('san', items=[Str('san')], required=True, empty=False),
            Dict(
                'cert_extensions',
                Dict(
                    'BasicConstraints',
                    Bool('ca', default=False),
                    Bool('enabled', default=False),
                    Int('path_length', null=True, default=None),
                    Bool('extension_critical', default=False)
                ),
                Dict(
                    'AuthorityKeyIdentifier',
                    Bool('authority_cert_issuer', default=False),
                    Bool('enabled', default=False),
                    Bool('extension_critical', default=False)
                ),
                Dict(
                    'ExtendedKeyUsage',
                    List('usages', items=[Str('usage', enum=EKU_OIDS)]),
                    Bool('enabled', default=False),
                    Bool('extension_critical', default=False)
                ),
                Dict(
                    'KeyUsage',
                    Bool('enabled', default=False),
                    Bool('digital_signature', default=False),
                    Bool('content_commitment', default=False),
                    Bool('key_encipherment', default=False),
                    Bool('data_encipherment', default=False),
                    Bool('key_agreement', default=False),
                    Bool('key_cert_sign', default=False),
                    Bool('crl_sign', default=False),
                    Bool('encipher_only', default=False),
                    Bool('decipher_only', default=False),
                    Bool('extension_critical', default=False)
                ),
                register=True
            ),
            register=True
        )
    )
    def generate_certificate(self, data):
        return generate_certificate(data)

    @accepts(Ref('certificate_cert_info'))
    def generate_self_signed_ca(self, data):
        return self.generate_certificate_authority(data)

    @accepts(Ref('certificate_cert_info'))
    def generate_certificate_authority(self, data):
        return generate_certificate_authority(data)

    @accepts(
        Dict(
            'sign_csr',
            Str('ca_certificate', required=True, max_length=None),
            Str('ca_privatekey', required=True, max_length=None),
            Str('csr', required=True, max_length=None),
            Str('csr_privatekey', required=True, max_length=None),
            Int('serial', required=True),
            Str('digest_algorithm', default='SHA256'),
            Ref('cert_extensions')
        )
    )
    def sign_csr_with_ca(self, data):
        return sign_csr_with_ca(data)
