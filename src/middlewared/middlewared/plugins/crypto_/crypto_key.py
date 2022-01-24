from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Ref, Str
from middlewared.service import Service
from middlewared.validators import Email

from .generate_utils import generate_builder, normalize_san
from .load_utils import load_private_key
from .key_utils import generate_private_key
from .utils import CERT_BACKEND_MAPPINGS, EC_CURVE_DEFAULT, EKU_OIDS


class CryptoKeyService(Service):

    class Config:
        private = True

    @accepts(
        Patch(
            'certificate_cert_info', 'generate_certificate_signing_request',
            ('rm', {'name': 'lifetime'})
        )
    )
    def generate_certificate_signing_request(self, data):
        key = generate_private_key({
            'type': data.get('key_type') or 'RSA',
            'curve': data.get('ec_curve') or EC_CURVE_DEFAULT,
            'key_length': data.get('key_length') or 2048
        })

        csr = generate_builder({
            'crypto_subject_name': {
                k: data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'san': normalize_san(data.get('san') or []),
            'serial': data.get('serial'),
            'lifetime': data.get('lifetime'),
            'csr': True
        })

        csr = self.middleware.call_sync('cryptokey.add_extensions', csr, data.get('cert_extensions', {}), key, None)

        csr = csr.sign(key, self.retrieve_signing_algorithm(data, key), default_backend())

        return (
            csr.public_bytes(serialization.Encoding.PEM).decode(),
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

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
        key = generate_private_key({
            'type': data.get('key_type') or 'RSA',
            'curve': data.get('ec_curve') or EC_CURVE_DEFAULT,
            'key_length': data.get('key_length') or 2048
        })

        if data.get('ca_privatekey'):
            ca_key = load_private_key(data['ca_privatekey'])
        else:
            ca_key = None

        san_list = normalize_san(data.get('san'))

        builder_data = {
            'crypto_subject_name': {
                k: data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'san': san_list,
            'serial': data.get('serial'),
            'lifetime': data.get('lifetime')
        }
        if data.get('ca_certificate'):
            ca_data = self.middleware.call_sync('cryptokey.load_certificate', data['ca_certificate'])
            builder_data['crypto_issuer_name'] = {
                k: ca_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            }
            issuer = x509.load_pem_x509_certificate(data['ca_certificate'].encode(), default_backend())
        else:
            issuer = None

        cert = self.middleware.call_sync(
            'cryptokey.add_extensions', generate_builder(builder_data), data.get('cert_extensions'), key, issuer
        )

        cert = cert.sign(
            ca_key or key, self.retrieve_signing_algorithm(data, ca_key or key), default_backend()
        )

        return (
            cert.public_bytes(serialization.Encoding.PEM).decode(),
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

    @accepts(
        Ref('certificate_cert_info')
    )
    def generate_self_signed_ca(self, data):
        return self.generate_certificate_authority(data)

    @accepts(
        Ref('certificate_cert_info')
    )
    def generate_certificate_authority(self, data):
        key = generate_private_key({
            'type': data.get('key_type') or 'RSA',
            'curve': data.get('ec_curve') or EC_CURVE_DEFAULT,
            'key_length': data.get('key_length') or 2048
        })

        if data.get('ca_privatekey'):
            ca_key = load_private_key(data['ca_privatekey'])
        else:
            ca_key = None

        san_list = normalize_san(data.get('san') or [])

        builder_data = {
            'crypto_subject_name': {
                k: data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'san': san_list,
            'serial': data.get('serial'),
            'lifetime': data.get('lifetime')
        }
        if data.get('ca_certificate'):
            ca_data = self.middleware.call_sync('cryptokey.load_certificate', data['ca_certificate'])
            builder_data['crypto_issuer_name'] = {
                k: ca_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            }
            issuer = x509.load_pem_x509_certificate(data['ca_certificate'].encode(), default_backend())
        else:
            issuer = None

        cert = self.middleware.call_sync(
            'cryptokey.add_extensions', generate_builder(builder_data), data.get('cert_extensions'), key, issuer
        )

        cert = cert.sign(
            ca_key or key, self.retrieve_signing_algorithm(data, ca_key or key), default_backend()
        )

        return (
            cert.public_bytes(serialization.Encoding.PEM).decode(),
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

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
        csr_data = self.middleware.call_sync('cryptokey.load_certificate_request', data['csr'])
        ca_data = self.middleware.call_sync('cryptokey.load_certificate', data['ca_certificate'])
        ca_key = load_private_key(data['ca_privatekey'])
        csr_key = load_private_key(data['csr_privatekey'])
        new_cert = generate_builder({
            'crypto_subject_name': {
                k: csr_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'crypto_issuer_name': {
                k: ca_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'serial': data['serial'],
            'san': normalize_san(csr_data.get('san'))
        })

        new_cert = self.middleware.call_sync(
            'cryptokey.add_extensions', new_cert, data.get('cert_extensions'), csr_key,
            x509.load_pem_x509_certificate(data['ca_certificate'].encode(), default_backend())
        )

        new_cert = new_cert.sign(
            ca_key, self.retrieve_signing_algorithm(data, ca_key), default_backend()
        )

        return new_cert.public_bytes(serialization.Encoding.PEM).decode()

    def retrieve_signing_algorithm(self, data, signing_key):
        if isinstance(signing_key, Ed25519PrivateKey):
            return None
        else:
            return getattr(hashes, data.get('digest_algorithm') or 'SHA256')()
