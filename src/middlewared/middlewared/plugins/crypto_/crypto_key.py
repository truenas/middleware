import datetime
import dateutil
import dateutil.parser
import ipaddress
import itertools
import random
import re

from OpenSSL import crypto, SSL
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

from .utils import DEFAULT_LIFETIME_DAYS, EC_CURVES, EC_CURVE_DEFAULT, EKU_OIDS, RE_CERTIFICATE


class CryptoKeyService(Service):

    backend_mappings = {
        'common_name': 'common',
        'country_name': 'country',
        'state_or_province_name': 'state',
        'locality_name': 'city',
        'organization_name': 'organization',
        'organizational_unit_name': 'organizational_unit',
        'email_address': 'email'
    }

    class Config:
        private = True

    def validate_cert_with_chain(self, cert, chain):
        check_cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
        store = crypto.X509Store()
        for chain_cert in itertools.chain.from_iterable(map(lambda c: RE_CERTIFICATE.findall(c), chain)):
            store.add_cert(
                crypto.load_certificate(crypto.FILETYPE_PEM, chain_cert)
            )

        store_ctx = crypto.X509StoreContext(store, check_cert)
        try:
            store_ctx.verify_certificate()
        except crypto.X509StoreContextError:
            return False
        else:
            return True

    def validate_certificate_with_key(self, certificate, private_key, schema_name, verrors, passphrase=None):
        if (
            (certificate and private_key) and
            all(k not in verrors for k in (f'{schema_name}.certificate', f'{schema_name}.privatekey'))
        ):
            public_key_obj = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
            private_key_obj = crypto.load_privatekey(
                crypto.FILETYPE_PEM,
                private_key,
                passphrase=passphrase.encode() if passphrase else None
            )

            try:
                context = SSL.Context(SSL.TLSv1_2_METHOD)
                context.use_certificate(public_key_obj)
                context.use_privatekey(private_key_obj)
                context.check_privatekey()
            except SSL.Error as e:
                verrors.add(
                    f'{schema_name}.privatekey',
                    f'Private key does not match certificate: {e}'
                )

        return verrors

    def validate_private_key(self, private_key, verrors, schema_name, passphrase=None):
        private_key_obj = self.load_private_key(private_key, passphrase)
        if not private_key_obj:
            verrors.add(
                f'{schema_name}.privatekey',
                'A valid private key is required, with a passphrase if one has been set.'
            )
        elif (
            'create' in schema_name and not isinstance(
                private_key_obj, (ec.EllipticCurvePrivateKey, Ed25519PrivateKey),
            ) and private_key_obj.key_size < 1024
        ):
            # When a cert/ca is being created, disallow keys with size less then 1024
            # Update is allowed for now for keeping compatibility with very old cert/keys
            # We do not do this check for any EC based key
            verrors.add(
                f'{schema_name}.privatekey',
                'Key size must be greater than or equal to 1024 bits.'
            )

    def parse_cert_date_string(self, date_value):
        t1 = dateutil.parser.parse(date_value)
        t2 = t1.astimezone(dateutil.tz.tzlocal())
        return t2.ctime()

    @accepts(
        Str('certificate', required=True, max_length=None)
    )
    def load_certificate(self, certificate):
        try:
            # digest_algorithm, lifetime, country, state, city, organization, organizational_unit,
            # email, common, san, serial, chain, fingerprint
            cert = crypto.load_certificate(
                crypto.FILETYPE_PEM,
                certificate
            )
        except crypto.Error:
            return {}
        else:
            cert_info = self.get_x509_subject(cert)

            valid_algos = ('SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512', 'ED25519')
            signature_algorithm = cert.get_signature_algorithm().decode()
            # Certs signed with RSA keys will have something like
            # sha256WithRSAEncryption
            # Certs signed with EC keys will have something like
            # ecdsa-with-SHA256
            m = re.match('^(.+)[Ww]ith', signature_algorithm)
            if m:
                cert_info['digest_algorithm'] = m.group(1).upper()

            if cert_info.get('digest_algorithm') not in valid_algos:
                cert_info['digest_algorithm'] = (signature_algorithm or '').split('-')[-1].strip()

            if cert_info['digest_algorithm'] not in valid_algos:
                # Let's log this please
                self.logger.debug(f'Failed to parse signature algorithm {signature_algorithm} for {certificate}')

            cert_info.update({
                'lifetime': (
                    dateutil.parser.parse(cert.get_notAfter()) - dateutil.parser.parse(cert.get_notBefore())
                ).days,
                'from': self.parse_cert_date_string(cert.get_notBefore()),
                'until': self.parse_cert_date_string(cert.get_notAfter()),
                'serial': cert.get_serial_number(),
                'chain': len(RE_CERTIFICATE.findall(certificate)) > 1,
                'fingerprint': cert.digest('sha1').decode(),
            })

            return cert_info

    def get_x509_subject(self, obj):
        cert_info = {
            'country': obj.get_subject().C,
            'state': obj.get_subject().ST,
            'city': obj.get_subject().L,
            'organization': obj.get_subject().O,
            'organizational_unit': obj.get_subject().OU,
            'common': obj.get_subject().CN,
            'san': [],
            'email': obj.get_subject().emailAddress,
            'DN': '',
            'subject_name_hash': obj.subject_name_hash() if not isinstance(obj, crypto.X509Req) else None,
            'extensions': {},
        }

        for ext in filter(
            lambda e: e.get_short_name().decode() != 'UNDEF',
            map(
                lambda i: obj.get_extension(i),
                range(obj.get_extension_count())
            ) if isinstance(obj, crypto.X509) else obj.get_extensions()
        ):
            if 'subjectAltName' == ext.get_short_name().decode():
                cert_info['san'] = [s.strip() for s in ext.__str__().split(',') if s]

            try:
                ext_name = re.sub(r"^(\S)", lambda m: m.group(1).upper(), ext.get_short_name().decode())
                cert_info['extensions'][ext_name] = 'Unable to parse extension'
                cert_info['extensions'][ext_name] = ext.__str__()
            except crypto.Error as e:
                # some certificates can have extensions with binary data which we can't parse without
                # explicit mapping for each extension. The current case covers the most of extensions nicely
                # and if it's required to map certain extensions which can't be handled by above we can do
                # so as users request.
                self.middleware.logger.error('Unable to parse extension: %s', e)

        dn = []
        subject = obj.get_subject()
        for k in filter(
            lambda k: k != 'subjectAltName' and hasattr(subject, k),
            map(lambda v: v[0].decode(), subject.get_components())
        ):
            dn.append(f'{k}={getattr(subject, k)}')

        cert_info['DN'] = f'/{"/".join(dn)}'

        if cert_info['san']:
            # We should always trust the extension instead of the subject for SAN
            cert_info['DN'] += f'/subjectAltName={", ".join(cert_info["san"])}'

        return cert_info

    @accepts(
        Str('csr', required=True, max_length=None)
    )
    def load_certificate_request(self, csr):
        try:
            csr_obj = crypto.load_certificate_request(crypto.FILETYPE_PEM, csr)
        except crypto.Error:
            return {}
        else:
            return self.get_x509_subject(csr_obj)

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
                k: data.get(v) for k, v in self.backend_mappings.items()
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
                k: data.get(v) for k, v in self.backend_mappings.items()
            },
            'san': san_list,
            'serial': data.get('serial'),
            'lifetime': data.get('lifetime')
        }
        if data.get('ca_certificate'):
            ca_data = self.load_certificate(data['ca_certificate'])
            builder_data['crypto_issuer_name'] = {
                k: ca_data.get(v) for k, v in self.backend_mappings.items()
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
                k: data.get(v) for k, v in self.backend_mappings.items()
            },
            'san': san_list,
            'serial': data.get('serial'),
            'lifetime': data.get('lifetime')
        }
        if data.get('ca_certificate'):
            ca_data = self.load_certificate(data['ca_certificate'])
            builder_data['crypto_issuer_name'] = {
                k: ca_data.get(v) for k, v in self.backend_mappings.items()
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
        csr_data = self.load_certificate_request(data['csr'])
        ca_data = self.load_certificate(data['ca_certificate'])
        ca_key = self.load_private_key(data['ca_privatekey'])
        csr_key = self.load_private_key(data['csr_privatekey'])
        new_cert = self.generate_builder({
            'crypto_subject_name': {
                k: csr_data.get(v) for k, v in self.backend_mappings.items()
            },
            'crypto_issuer_name': {
                k: ca_data.get(v) for k, v in self.backend_mappings.items()
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

    def generate_crl(self, ca, certs, next_update=1):
        # There is a tricky case here - what happens if the root CA is compromised ?
        # In normal world scenarios, that CA is removed from app's trust store and any
        # subsequent certs it had issues wouldn't be validated by the app then. Making a CRL
        # for a revoked root CA in normal cases doesn't make sense as the thief can sign a
        # counter CRL saying that everything is fine. As our environment is controlled,
        # i think we are safe to create a crl for root CA as well which we can publish for
        # services which make use of it i.e openvpn and they'll know that the certs/ca's have been
        # compromised.
        #
        # `ca` is root ca from where the chain `certs` starts.
        # `certs` is a list of all certs ca inclusive which are to be
        # included in the CRL ( if root ca is compromised, it will be in `certs` as well ).

        private_key = self.load_private_key(
            ca['privatekey']
        )
        ca_cert = x509.load_pem_x509_certificate(ca['certificate'].encode(), default_backend())

        if not private_key:
            return None

        ca_data = self.load_certificate(ca['certificate'])

        issuer = {
            k: ca_data.get(v) for k, v in self.backend_mappings.items()
        }

        crl_builder = x509.CertificateRevocationListBuilder().issuer_name(x509.Name([
            x509.NameAttribute(getattr(NameOID, k.upper()), v)
            for k, v in issuer.items() if v
        ])).last_update(
            datetime.datetime.utcnow()
        ).next_update(
            datetime.datetime.utcnow() + datetime.timedelta(next_update, 300, 0)
        )

        for cert in certs:
            crl_builder = crl_builder.add_revoked_certificate(
                x509.RevokedCertificateBuilder().serial_number(
                    self.load_certificate(cert['certificate'])['serial']
                ).revocation_date(
                    cert['revoked_date']
                ).build(
                    default_backend()
                )
            )

        # https://www.ietf.org/rfc/rfc5280.txt
        # We should add AuthorityKeyIdentifier and CRLNumber at the very least

        crl = crl_builder.add_extension(
            x509.AuthorityKeyIdentifier(
                x509.SubjectKeyIdentifier.from_public_key(
                    ca_cert.public_key()
                ).digest, [x509.DirectoryName(
                    x509.Name([
                        x509.NameAttribute(getattr(NameOID, k.upper()), v)
                        for k, v in issuer.items() if v
                    ])
                )], ca_cert.serial_number
            ), False
        ).add_extension(
            x509.CRLNumber(1), False
        ).sign(
            private_key=private_key, algorithm=self.retrieve_signing_algorithm({}, private_key),
            backend=default_backend()
        )

        return crl.public_bytes(
            serialization.Encoding.PEM
        ).decode()
