import datetime
import ipaddress
import random

from contextlib import suppress

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Ref, Str
from middlewared.service import Service
from middlewared.validators import Email, IpAddress

from .utils import CERT_BACKEND_MAPPINGS, DEFAULT_LIFETIME_DAYS, EC_CURVES, EC_CURVE_DEFAULT, EKU_OIDS


class CryptoKeyService(Service):

    class Config:
        private = True

    def generate_self_signed_certificate(self):
        cert = self.generate_builder({
            'crypto_subject_name': {
                'country_name': 'US',
                'organization_name': 'iXsystems',
                'common_name': 'localhost',
                'email_address': 'info@ixsystems.com',
                'state_or_province_name': 'Tennessee',
                'locality_name': 'Maryville',
            },
            'lifetime': DEFAULT_LIFETIME_DAYS,
            'san': self.normalize_san(['localhost'])
        })
        key = self.generate_private_key({
            'serialize': False,
            'key_length': 2048,
            'type': 'RSA'
        })

        cert = cert.public_key(
            key.public_key()
        ).add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False
        ).sign(
            key, hashes.SHA256(), default_backend()
        )

        return (
            cert.public_bytes(serialization.Encoding.PEM).decode(),
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

    def normalize_san(self, san_list):
        # TODO: ADD MORE TYPES WRT RFC'S
        normalized = []
        ip_validator = IpAddress()
        for count, san in enumerate(san_list or []):
            try:
                ip_validator(san)
            except ValueError:
                normalized.append(['DNS', san])
            else:
                normalized.append(['IP', san])

        return normalized

    @accepts(
        Patch(
            'certificate_cert_info', 'generate_certificate_signing_request',
            ('rm', {'name': 'lifetime'})
        )
    )
    def generate_certificate_signing_request(self, data):
        key = self.generate_private_key({
            'type': data.get('key_type') or 'RSA',
            'curve': data.get('ec_curve') or EC_CURVE_DEFAULT,
            'key_length': data.get('key_length') or 2048
        })

        csr = self.generate_builder({
            'crypto_subject_name': {
                k: data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'san': self.normalize_san(data.get('san') or []),
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
        key = self.generate_private_key({
            'type': data.get('key_type') or 'RSA',
            'curve': data.get('ec_curve') or EC_CURVE_DEFAULT,
            'key_length': data.get('key_length') or 2048
        })

        if data.get('ca_privatekey'):
            ca_key = self.load_private_key(data['ca_privatekey'])
        else:
            ca_key = None

        san_list = self.normalize_san(data.get('san'))

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
            'cryptokey.add_extensions', self.generate_builder(builder_data), data.get('cert_extensions'), key, issuer
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
        key = self.generate_private_key({
            'type': data.get('key_type') or 'RSA',
            'curve': data.get('ec_curve') or EC_CURVE_DEFAULT,
            'key_length': data.get('key_length') or 2048
        })

        if data.get('ca_privatekey'):
            ca_key = self.load_private_key(data['ca_privatekey'])
        else:
            ca_key = None

        san_list = self.normalize_san(data.get('san') or [])

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
            'cryptokey.add_extensions', self.generate_builder(builder_data), data.get('cert_extensions'), key, issuer
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
        ca_key = self.load_private_key(data['ca_privatekey'])
        csr_key = self.load_private_key(data['csr_privatekey'])
        new_cert = self.generate_builder({
            'crypto_subject_name': {
                k: csr_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'crypto_issuer_name': {
                k: ca_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()
            },
            'serial': data['serial'],
            'san': self.normalize_san(csr_data.get('san'))
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

    def generate_builder(self, options):
        # We expect backend_mapping keys for crypto_subject_name attr in options and for crypto_issuer_name as well
        data = {}
        for key in ('crypto_subject_name', 'crypto_issuer_name'):
            data[key] = x509.Name([
                x509.NameAttribute(getattr(NameOID, k.upper()), v)
                for k, v in (options.get(key) or {}).items() if v
            ])
        if not data['crypto_issuer_name']:
            data['crypto_issuer_name'] = data['crypto_subject_name']

        # Lifetime represents no of days
        # Let's normalize lifetime value
        not_valid_before = datetime.datetime.utcnow()
        not_valid_after = datetime.datetime.utcnow() + datetime.timedelta(
            days=options.get('lifetime') or DEFAULT_LIFETIME_DAYS
        )

        # Let's normalize `san`
        san = x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address(v)) if t == 'IP' else x509.DNSName(v)
            for t, v in options.get('san') or []
        ])

        builder = x509.CertificateSigningRequestBuilder if options.get('csr') else x509.CertificateBuilder

        cert = builder(
            subject_name=data['crypto_subject_name']
        )

        if not options.get('csr'):
            cert = cert.issuer_name(
                data['crypto_issuer_name']
            ).not_valid_before(
                not_valid_before
            ).not_valid_after(
                not_valid_after
            ).serial_number(options.get('serial') or random.randint(1000, pow(2, 30)))

        if san:
            cert = cert.add_extension(san, False)

        return cert

    @accepts(
        Dict(
            'generate_private_key',
            Bool('serialize', default=False),
            Int('key_length', default=2048),
            Str('type', default='RSA', enum=['RSA', 'EC']),
            Str('curve', enum=EC_CURVES, default='BrainpoolP384R1')
        )
    )
    def generate_private_key(self, options):
        # We should make sure to return in PEM format
        # Reason for using PKCS8
        # https://stackoverflow.com/questions/48958304/pkcs1-and-pkcs8-format-for-rsa-private-key

        if options.get('type') == 'EC':
            if options['curve'] == 'ed25519':
                key = Ed25519PrivateKey.generate()
            else:
                key = ec.generate_private_key(
                    getattr(ec, options.get('curve')),
                    default_backend()
                )
        else:
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=options.get('key_length'),
                backend=default_backend()
            )

        if options.get('serialize'):
            return key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        else:
            return key

    def load_private_key(self, key_string, passphrase=None):
        with suppress(ValueError, TypeError, AttributeError):
            return serialization.load_pem_private_key(
                key_string.encode(),
                password=passphrase.encode() if passphrase else None,
                backend=default_backend()
            )

    def export_private_key(self, buffer, passphrase=None):
        key = self.load_private_key(buffer, passphrase)
        if key:
            return key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
