import copy
import datetime
import dateutil
import dateutil.parser
import inspect
import ipaddress
import itertools
import josepy as jose
import os
import random
import re
import subprocess

from middlewared.async_validators import validate_country
from middlewared.schema import accepts, Bool, Datetime, Dict, Int, List, OROperator, Patch, Ref, returns, Str
from middlewared.service import CallError, CRUDService, job, periodic, private, Service, skip_arg, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.validators import Email, IpAddress, Range
from middlewared.utils import osc

from acme import errors, messages
from OpenSSL import crypto, SSL
from contextlib import suppress

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization


CA_TYPE_EXISTING = 0x01
CA_TYPE_INTERNAL = 0x02
CA_TYPE_INTERMEDIATE = 0x04
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_INTERNAL = 0x10
CERT_TYPE_CSR = 0x20

CERT_ROOT_PATH = '/etc/certificates'
CERT_CA_ROOT_PATH = '/etc/certificates/CA'
EKU_OIDS = [i for i in dir(x509.oid.ExtendedKeyUsageOID) if not i.startswith('__')]
NOT_VALID_AFTER_DEFAULT = 825
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)


def get_cert_info_from_data(data):
    cert_info_keys = [
        'key_length', 'country', 'state', 'city', 'organization', 'common', 'key_type', 'ec_curve',
        'san', 'serial', 'email', 'lifetime', 'digest_algorithm', 'organizational_unit'
    ]
    return {key: data.get(key) for key in cert_info_keys if data.get(key)}


def check_dependencies(middleware, cert_type, id):
    if cert_type == 'CA':
        key = 'truenas_certificate_authorities'
        method = 'certificateauthority.check_dependencies'
    else:
        key = 'truenas_certificates'
        method = 'certificate.check_dependencies'

    middleware.call_sync(method, id)

    chart_releases = middleware.call_sync(
        'chart.release.query', [[f'resources.{key}', 'rin', id]], {'extra': {'retrieve_resources': True}}
    )
    if chart_releases:
        raise CallError(
            f'Certificate{" Authority" if cert_type == "CA" else ""} cannot be deleted as it is being used by '
            f'{", ".join([c["id"] for c in chart_releases])} chart release(s).'
        )


async def validate_cert_name(middleware, cert_name, datastore, verrors, name):
    certs = await middleware.call(
        'datastore.query',
        datastore,
        [('cert_name', '=', cert_name)]
    )
    if certs:
        verrors.add(
            name,
            'A certificate with this name already exists'
        )

    if cert_name in ("external", "self-signed", "external - signature pending"):
        verrors.add(
            name,
            f'{cert_name} is a reserved internal keyword for Certificate Management'
        )
    reg = re.search(r'^[a-z0-9_\-]+$', cert_name or '', re.I)
    if not reg:
        verrors.add(
            name,
            'Use alphanumeric characters, "_" and "-".'
        )


def _set_required(name):
    def set_r(attr):
        attr.required = True
    return {'name': name, 'method': set_r}


async def _validate_common_attributes(middleware, data, verrors, schema_name):

    country = data.get('country')
    if country:
        await validate_country(middleware, country, verrors, f'{schema_name}.country')

    certificate = data.get('certificate')
    if certificate:
        matches = RE_CERTIFICATE.findall(certificate)

        if not matches or not await middleware.call('cryptokey.load_certificate', certificate):
            verrors.add(
                f'{schema_name}.certificate',
                'Not a valid certificate'
            )

    private_key = data.get('privatekey')
    passphrase = data.get('passphrase')
    if private_key:
        await middleware.call('cryptokey.validate_private_key', private_key, verrors, schema_name, passphrase)

    signedby = data.get('signedby')
    if signedby:
        valid_signing_ca = await middleware.call(
            'certificateauthority.query',
            [
                ('certificate', '!=', None),
                ('privatekey', '!=', None),
                ('certificate', '!=', ''),
                ('privatekey', '!=', ''),
                ('id', '=', signedby)
            ],
        )

        if not valid_signing_ca:
            verrors.add(
                f'{schema_name}.signedby',
                'Please provide a valid signing authority'
            )

    csr = data.get('CSR')
    if csr:
        if not await middleware.call('cryptokey.load_certificate_request', csr):
            verrors.add(
                f'{schema_name}.CSR',
                'Please provide a valid CSR'
            )

    csr_id = data.get('csr_id')
    if csr_id and not await middleware.call('certificate.query', [['id', '=', csr_id], ['CSR', '!=', None]]):
        verrors.add(
            f'{schema_name}.csr_id',
            'Please provide a valid csr_id which has a valid CSR filed'
        )

    await middleware.call(
        'cryptokey.validate_certificate_with_key', certificate, private_key, schema_name, verrors, passphrase
    )

    key_type = data.get('key_type')
    if key_type:
        if key_type != 'EC':
            if not data.get('key_length'):
                verrors.add(
                    f'{schema_name}.key_length',
                    'RSA-based keys require an entry in this field.'
                )
            if not data.get('digest_algorithm'):
                verrors.add(
                    f'{schema_name}.digest_algorithm',
                    'This field is required.'
                )

    if not verrors and data.get('cert_extensions'):
        verrors.extend(
            (await middleware.call('cryptokey.validate_extensions', data['cert_extensions'], schema_name))
        )


class CryptoKeyService(Service):

    ec_curve_default = 'BrainpoolP384R1'

    ec_curves = [
        'BrainpoolP512R1',
        'BrainpoolP384R1',
        'BrainpoolP256R1',
        'SECP256K1',
        'ed25519',
    ]

    backend_mappings = {
        'common_name': 'common',
        'country_name': 'country',
        'state_or_province_name': 'state',
        'locality_name': 'city',
        'organization_name': 'organization',
        'organizational_unit_name': 'organizational_unit',
        'email_address': 'email'
    }

    EXTENSIONS = {}

    class Config:
        private = True

    @staticmethod
    def extensions():
        if not CryptoKeyService.EXTENSIONS:
            # For now we only support the following extensions
            # We also support SubjectAlternativeName but as we include that natively if the user provides it
            # we don't expose it to the end user as an extension making the process for the end user easier to
            # create a certificate/ca as most wouldn't even want to know what extension is or does.
            # Apart from this we also add subjectKeyIdentifier automatically
            supported = [
                'BasicConstraints', 'AuthorityKeyIdentifier',
                'ExtendedKeyUsage', 'KeyUsage'
            ]

            for attr in supported:
                attr_obj = getattr(x509.extensions, attr)
                CryptoKeyService.EXTENSIONS[attr] = inspect.getfullargspec(attr_obj.__init__).args[1:]

        return CryptoKeyService.EXTENSIONS

    def add_extensions(self, cert, extensions_data, key, issuer=None):
        # issuer must be a certificate object
        # By default we add the following
        if not isinstance(cert, x509.CertificateSigningRequestBuilder):
            cert = cert.public_key(
                key.public_key()
            ).add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False
            )

        for extension in filter(lambda v: v[1]['enabled'], extensions_data.items()):
            klass = getattr(x509.extensions, extension[0])
            cert = cert.add_extension(
                klass(*self.get_extension_params(extension, cert, issuer)),
                extension[1].get('extension_critical') or False
            )

        return cert

    def get_extension_params(self, extension, cert=None, issuer=None):
        params = []

        if extension[0] == 'BasicConstraints':
            params = [extension[1].get('ca'), extension[1].get('path_length')]
        elif extension[0] == 'ExtendedKeyUsage':
            usages = []
            for ext_usage in extension[1].get('usages', []):
                usages.append(getattr(x509.oid.ExtendedKeyUsageOID, ext_usage))
            params = [usages]
        elif extension[0] == 'KeyUsage':
            params = [extension[1].get(k, False) for k in self.extensions()['KeyUsage']]
        elif extension[0] == 'AuthorityKeyIdentifier':
            params = [
                x509.SubjectKeyIdentifier.from_public_key(
                    issuer.public_key() if issuer else cert._public_key
                ).digest if cert or issuer else None,
                None, None
            ]

            if extension[1]['authority_cert_issuer'] and cert:
                params[1:] = [
                    [x509.DirectoryName(cert._issuer_name)],
                    issuer.serial_number if issuer else cert._serial_number
                ]

        return params

    @accepts(
        Ref('cert_extensions'),
        Str('schema')
    )
    def validate_extensions(self, extensions_data, schema):
        # We do not need to validate some extensions like `AuthorityKeyIdentifier`.
        # They are generated from the cert/ca's public key contents. So we skip these.

        skip_extension = ['AuthorityKeyIdentifier']
        verrors = ValidationErrors()

        for extension in filter(
            lambda v: v[1]['enabled'] and v[0] not in skip_extension,
            extensions_data.items()
        ):
            klass = getattr(x509.extensions, extension[0])
            try:
                klass(*self.get_extension_params(extension))
            except Exception as e:
                verrors.add(
                    f'{schema}.{extension[0]}',
                    f'Please provide valid values for {extension[0]}: {e}'
                )

        if extensions_data['KeyUsage']['enabled'] and extensions_data['KeyUsage']['key_cert_sign']:
            if not extensions_data['BasicConstraints']['enabled'] or not extensions_data[
                'BasicConstraints'
            ]['ca']:
                verrors.add(
                    f'{schema}.BasicConstraints',
                    'Please enable ca when key_cert_sign is set in KeyUsage as per RFC 5280.'
                )

        if extensions_data['ExtendedKeyUsage']['enabled'] and not extensions_data['ExtendedKeyUsage']['usages']:
            verrors.add(
                f'{schema}.ExtendedKeyUsage.usages',
                'Please specify at least one USAGE for this extension.'
            )

        return verrors

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
            'lifetime': NOT_VALID_AFTER_DEFAULT,
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
            'curve': data.get('ec_curve') or self.ec_curve_default,
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

        csr = self.add_extensions(csr, data.get('cert_extensions', {}), key, None)

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
            'curve': data.get('ec_curve') or self.ec_curve_default,
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

        cert = self.generate_builder(builder_data)

        cert = self.add_extensions(cert, data.get('cert_extensions'), key, issuer)

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
            'curve': data.get('ec_curve') or self.ec_curve_default,
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

        cert = self.generate_builder(builder_data)

        cert = self.add_extensions(cert, data.get('cert_extensions'), key, issuer)

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

        new_cert = self.add_extensions(
            new_cert, data.get('cert_extensions'), csr_key,
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
            days=options.get('lifetime') or NOT_VALID_AFTER_DEFAULT
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
            Str('curve', enum=ec_curves, default='BrainpoolP384R1')
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


class CertificateModel(sa.Model):
    __tablename__ = 'system_certificate'

    id = sa.Column(sa.Integer(), primary_key=True)
    cert_type = sa.Column(sa.Integer())
    cert_name = sa.Column(sa.String(120), unique=True)
    cert_certificate = sa.Column(sa.Text(), nullable=True)
    cert_privatekey = sa.Column(sa.EncryptedText(), nullable=True)
    cert_CSR = sa.Column(sa.Text(), nullable=True)
    cert_signedby_id = sa.Column(sa.ForeignKey('system_certificateauthority.id'), index=True, nullable=True)
    cert_acme_uri = sa.Column(sa.String(200), nullable=True)
    cert_domains_authenticators = sa.Column(sa.JSON(encrypted=True), nullable=True)
    cert_renew_days = sa.Column(sa.Integer(), nullable=True, default=10)
    cert_acme_id = sa.Column(sa.ForeignKey('system_acmeregistration.id'), index=True, nullable=True)
    cert_revoked_date = sa.Column(sa.DateTime(), nullable=True)


class CertificateService(CRUDService):

    class Config:
        datastore = 'system.certificate'
        datastore_extend = 'certificate.cert_extend'
        datastore_prefix = 'cert_'
        cli_namespace = 'system.certificate'

    ENTRY = Dict(
        'certificate_entry',
        Int('id'),
        Int('type'),
        Str('name'),
        Str('certificate', null=True, max_length=None),
        Str('privatekey', null=True, max_length=None),
        Str('CSR', null=True, max_length=None),
        Str('acme_uri', null=True),
        Dict('domains_authenticators', additional_attrs=True, null=True),
        Int('renew_days'),
        Datetime('revoked_date', null=True),
        Dict('signedby', additional_attrs=True, null=True),
        Str('root_path'),
        Dict('acme', additional_attrs=True, null=True),
        Str('certificate_path', null=True),
        Str('privatekey_path', null=True),
        Str('csr_path', null=True),
        Str('cert_type'),
        Bool('revoked'),
        OROperator(Str('issuer', null=True), Dict('issuer', additional_attrs=True, null=True), name='issuer'),
        List('chain_list', items=[Str('certificate', max_length=None)]),
        Str('country', null=True),
        Str('state', null=True),
        Str('city', null=True),
        Str('organization', null=True),
        Str('organizational_unit', null=True),
        List('san', items=[Str('san_entry')], null=True),
        Str('email', null=True),
        Str('DN', null=True),
        Str('subject_name_hash', null=True),
        Str('digest_algorithm', null=True),
        Str('from', null=True),
        Str('common', null=True, max_length=None),
        Str('until', null=True),
        Str('fingerprint', null=True),
        Str('key_type', null=True),
        Str('internal', null=True),
        Int('lifetime', null=True),
        Int('serial', null=True),
        Int('key_length', null=True),
        Bool('chain', null=True),
        Bool('CA_type_existing'),
        Bool('CA_type_internal'),
        Bool('CA_type_intermediate'),
        Bool('cert_type_existing'),
        Bool('cert_type_internal'),
        Bool('cert_type_CSR'),
        Bool('parsed'),
        Bool('can_be_revoked'),
        Dict('extensions', additional_attrs=True),
        List('revoked_certs'),
        Str('crl_path'),
        Int('signed_certificates'),
    )

    PROFILES = {
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_functions = {
            'CERTIFICATE_CREATE_INTERNAL': self.create_internal,
            'CERTIFICATE_CREATE_IMPORTED': self.__create_imported_certificate,
            'CERTIFICATE_CREATE_IMPORTED_CSR': self.__create_imported_csr,
            'CERTIFICATE_CREATE_CSR': self.create_csr,
            'CERTIFICATE_CREATE_ACME': self.__create_acme_certificate,
        }

    @accepts()
    @returns(Dict(
        'certificate_profiles',
        *[Dict(profile, additional_attrs=True) for profile in PROFILES]
    ))
    async def profiles(self):
        """
        Returns a dictionary of predefined options for specific use cases i.e openvpn client/server
        configurations which can be used for creating certificates.
        """
        return self.PROFILES

    @accepts()
    @returns(Ref('country_choices'))
    async def country_choices(self):
        """
        Returns country choices for creating a certificate/csr.
        """
        return await self.middleware.call('system.general.country_choices')

    @private
    async def cert_extend(self, cert):
        """Extend certificate with some useful attributes."""

        if cert.get('signedby'):

            # We query for signedby again to make sure it's keys do not have the "cert_" prefix and it has gone through
            # the cert_extend method
            # Datastore query is used instead of certificate.query to stop an infinite recursive loop

            cert['signedby'] = await self.middleware.call(
                'datastore.query',
                'system.certificateauthority',
                [('id', '=', cert['signedby']['id'])],
                {
                    'prefix': 'cert_',
                    'extend': 'certificate.cert_extend',
                    'get': True
                }
            )

        # Remove ACME related keys if cert is not an ACME based cert
        if not cert.get('acme'):
            for key in ['acme', 'acme_uri', 'domains_authenticators', 'renew_days']:
                cert.pop(key, None)

        if cert['type'] in (
                CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE
        ):
            root_path = CERT_CA_ROOT_PATH
        else:
            root_path = CERT_ROOT_PATH
        cert['root_path'] = root_path
        cert['certificate_path'] = os.path.join(
            root_path, f'{cert["name"]}.crt'
        )
        cert['privatekey_path'] = os.path.join(
            root_path, f'{cert["name"]}.key'
        )
        cert['csr_path'] = os.path.join(
            root_path, f'{cert["name"]}.csr'
        )

        cert['cert_type'] = 'CA' if root_path == CERT_CA_ROOT_PATH else 'CERTIFICATE'
        cert['revoked'] = bool(cert['revoked_date'])

        if cert['cert_type'] == 'CA':
            # TODO: Should we look for intermediate ca's as well which this ca has signed ?
            cert['signed_certificates'] = len((
                await self.middleware.call(
                    'datastore.query',
                    'system.certificate',
                    [['signedby', '=', cert['id']]],
                    {'prefix': 'cert_'}
                )
            ))

            ca_chain = await self.middleware.call('certificateauthority.get_ca_chain', cert['id'])
            cert.update({
                'revoked_certs': list(filter(lambda c: c['revoked_date'], ca_chain)),
                'crl_path': os.path.join(root_path, f'{cert["name"]}.crl'),
                'can_be_revoked': bool(cert['privatekey']) and not cert['revoked'],
            })
        else:
            cert['can_be_revoked'] = bool(cert['signedby']) and not cert['revoked']

        if not os.path.exists(root_path):
            os.makedirs(root_path, 0o755, exist_ok=True)

        def cert_issuer(cert):
            issuer = None
            if cert['type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING):
                issuer = "external"
            elif cert['type'] == CA_TYPE_INTERNAL:
                issuer = "self-signed"
            elif cert['type'] in (CERT_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE):
                issuer = cert['signedby']
            elif cert['type'] == CERT_TYPE_CSR:
                issuer = "external - signature pending"
            return issuer

        cert['issuer'] = cert_issuer(cert)

        cert['chain_list'] = []
        certs = []
        if len(RE_CERTIFICATE.findall(cert['certificate'] or '')) > 1:
            certs = RE_CERTIFICATE.findall(cert['certificate'])
        elif cert['type'] != CERT_TYPE_CSR:
            certs = [cert['certificate']]
            signing_CA = cert['issuer']
            # Recursively get all internal/intermediate certificates
            # FIXME: NONE HAS BEEN ADDED IN THE FOLLOWING CHECK FOR CSR'S WHICH HAVE BEEN SIGNED BY A CA
            while signing_CA not in ["external", "self-signed", "external - signature pending", None]:
                certs.append(signing_CA['certificate'])
                signing_CA['issuer'] = cert_issuer(signing_CA)
                signing_CA = signing_CA['issuer']

        failed_parsing = False
        for c in certs:
            if c and await self.middleware.call('cryptokey.load_certificate', c):
                cert['chain_list'].append(c)
            else:
                self.cert_extend_report_error('certificate chain', cert)
                break

        if certs:
            # This indicates cert is not CSR and a cert
            cert_data = await self.middleware.call('cryptokey.load_certificate', cert['certificate'])
            cert.update(cert_data)
            if not cert_data:
                self.cert_extend_report_error('certificate', cert)
                failed_parsing = True

        if cert['privatekey']:
            key_obj = await self.middleware.call('cryptokey.load_private_key', cert['privatekey'])
            if key_obj:
                if isinstance(key_obj, Ed25519PrivateKey):
                    cert['key_length'] = 32
                else:
                    cert['key_length'] = key_obj.key_size
                if isinstance(key_obj, (ec.EllipticCurvePrivateKey, Ed25519PrivateKey)):
                    cert['key_type'] = 'EC'
                elif isinstance(key_obj, rsa.RSAPrivateKey):
                    cert['key_type'] = 'RSA'
                elif isinstance(key_obj, dsa.DSAPrivateKey):
                    cert['key_type'] = 'DSA'
                else:
                    cert['key_type'] = 'OTHER'
            else:
                self.cert_extend_report_error('private key', cert)
                cert['key_length'] = cert['key_type'] = None
        else:
            cert['key_length'] = cert['key_type'] = None

        if cert['type'] == CERT_TYPE_CSR:
            csr_data = await self.middleware.call('cryptokey.load_certificate_request', cert['CSR'])
            if csr_data:
                cert.update(csr_data)

                cert.update({k: None for k in ('from', 'until')})  # CSR's don't have from, until - normalizing keys
            else:
                self.cert_extend_report_error('csr', cert)
                failed_parsing = True

        if failed_parsing:
            # Normalizing cert/csr
            # Should we perhaps set the value to something like "MALFORMED_CERTIFICATE" for this list off attrs ?
            cert.update({
                key: None for key in [
                    'digest_algorithm', 'lifetime', 'country', 'state', 'city', 'from', 'until',
                    'organization', 'organizational_unit', 'email', 'common', 'san', 'serial',
                    'fingerprint', 'extensions'
                ]
            })

        cert['parsed'] = not failed_parsing

        cert['internal'] = 'NO' if cert['type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING) else 'YES'
        cert['CA_type_existing'] = bool(cert['type'] & CA_TYPE_EXISTING)
        cert['CA_type_internal'] = bool(cert['type'] & CA_TYPE_INTERNAL)
        cert['CA_type_intermediate'] = bool(cert['type'] & CA_TYPE_INTERMEDIATE)
        cert['cert_type_existing'] = bool(cert['type'] & CERT_TYPE_EXISTING)
        cert['cert_type_internal'] = bool(cert['type'] & CERT_TYPE_INTERNAL)
        cert['cert_type_CSR'] = bool(cert['type'] & CERT_TYPE_CSR)

        return cert

    cert_extend_reported_errors = set()

    @private
    def cert_extend_report_error(self, title, cert):
        item = (title, cert['name'])
        if item not in self.cert_extend_reported_errors:
            self.logger.debug('Failed to load %s of %s', title, cert['name'])
            self.cert_extend_reported_errors.add(item)

    # HELPER METHODS

    @private
    async def cert_services_validation(self, id, schema_name, raise_verrors=True):
        # General method to check certificate health wrt usage in services
        cert = await self.middleware.call('certificate.query', [['id', '=', id]])
        verrors = ValidationErrors()
        if cert:
            cert = cert[0]
            if cert['cert_type'] != 'CERTIFICATE' or cert['cert_type_CSR']:
                verrors.add(
                    schema_name,
                    'Selected certificate id is not a valid certificate'
                )
            elif not cert.get('fingerprint'):
                verrors.add(
                    schema_name,
                    f'{cert["name"]} certificate is malformed'
                )

            if not cert['privatekey']:
                verrors.add(
                    schema_name,
                    'Selected certificate does not have a private key'
                )
            elif not cert['key_length']:
                verrors.add(
                    schema_name,
                    'Failed to parse certificate\'s private key'
                )
            elif cert['key_type'] != 'EC' and cert['key_length'] < 1024:
                verrors.add(
                    schema_name,
                    f'{cert["name"]}\'s private key size is less then 1024 bits'
                )

            if cert['revoked']:
                verrors.add(
                    schema_name,
                    'This certificate is revoked'
                )
        else:
            verrors.add(
                schema_name,
                f'No Certificate found with the provided id: {id}'
            )

        if raise_verrors:
            verrors.check()
        else:
            return verrors

    @private
    async def validate_common_attributes(self, data, schema_name):
        verrors = ValidationErrors()

        await _validate_common_attributes(self.middleware, data, verrors, schema_name)

        return verrors

    @private
    async def get_domain_names(self, cert_id):
        data = await self._get_instance(int(cert_id))
        names = [data['common']] if data['common'] else []
        names.extend(data['san'])
        return names

    @periodic(86400)
    @private
    @job(lock='acme_cert_renewal')
    def renew_certs(self, job):
        certs = self.middleware.call_sync(
            'certificate.query',
            [['acme', '!=', None]]
        )

        progress = 0
        for cert in certs:
            progress += (100 / len(certs))

            if (
                datetime.datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - datetime.datetime.utcnow()
            ).days < cert['renew_days']:
                # renew cert
                self.logger.debug(f'Renewing certificate {cert["name"]}')
                final_order = self.middleware.call_sync(
                    'acme.issue_certificate',
                    job, progress / 4, {
                        'tos': True,
                        'acme_directory_uri': cert['acme']['directory'],
                        'dns_mapping': cert['domains_authenticators'],
                    },
                    cert
                )

                self.middleware.call_sync(
                    'datastore.update',
                    self._config.datastore,
                    cert['id'],
                    {
                        'certificate': final_order.fullchain_pem,
                        'acme_uri': final_order.uri
                    },
                    {'prefix': self._config.datastore_prefix}
                )
                try:
                    self.middleware.call_sync('certificate.redeploy_cert_attachments', cert['id'])
                except Exception:
                    self.logger.error(
                        'Failed to reload services dependent on %r certificate', cert['name'], exc_info=True
                    )

            job.set_progress(progress)

    @accepts()
    @returns(Dict('acme_server_choices', additional_attrs=True))
    async def acme_server_choices(self):
        """
        Dictionary of popular ACME Servers with their directory URI endpoints which we display automatically
        in UI
        """
        return {
            'https://acme-staging-v02.api.letsencrypt.org/directory': 'Let\'s Encrypt Staging Directory',
            'https://acme-v02.api.letsencrypt.org/directory': 'Let\'s Encrypt Production Directory'
        }

    @accepts()
    @returns(Dict(
        'ec_curve_choices',
        *[Str(k, enum=[k]) for k in CryptoKeyService.ec_curves]
    ))
    async def ec_curve_choices(self):
        """
        Dictionary of supported EC curves.
        """
        return {k: k for k in CryptoKeyService.ec_curves}

    @accepts()
    @returns(Dict(
        'private_key_type_choices',
        *[Str(k, enum=[k]) for k in ('RSA', 'EC')]
    ))
    async def key_type_choices(self):
        """
        Dictionary of supported key types for certificates.
        """
        return {k: k for k in ['RSA', 'EC']}

    @accepts()
    @returns(Dict(
        'extended_key_usage_choices',
        *[Str(k, enum=[k]) for k in EKU_OIDS]
    ))
    async def extended_key_usage_choices(self):
        """
        Dictionary of choices for `ExtendedKeyUsage` extension which can be passed over to `usages` attribute.
        """
        return {k: k for k in EKU_OIDS}

    @private
    async def dhparam(self):
        return '/data/dhparam.pem'

    @private
    @job()
    def dhparam_setup(self, job):
        dhparam_path = self.middleware.call_sync('certificate.dhparam')
        if not os.path.exists(dhparam_path) or os.stat(dhparam_path).st_size == 0:
            with open('/dev/console', 'wb') as console:
                with open(dhparam_path, 'wb') as f:
                    if osc.IS_FREEBSD:
                        rand = '/dev/random'
                    else:
                        rand = '/dev/urandom'
                    subprocess.run(['openssl', 'dhparam', '-rand', rand, '2048'], stdout=f, stderr=console, check=True)

    # CREATE METHODS FOR CREATING CERTIFICATES
    # "do_create" IS CALLED FIRST AND THEN BASED ON THE TYPE OF THE CERTIFICATE WHICH IS TO BE CREATED THE
    # APPROPRIATE METHOD IS CALLED
    # FOLLOWING TYPES ARE SUPPORTED
    # CREATE_TYPE ( STRING )          - METHOD CALLED
    # CERTIFICATE_CREATE_INTERNAL     - create_internal
    # CERTIFICATE_CREATE_IMPORTED     - __create_imported_certificate
    # CERTIFICATE_CREATE_IMPORTED_CSR - __create_imported_csr
    # CERTIFICATE_CREATE_CSR          - create_csr
    # CERTIFICATE_CREATE_ACME         - __create_acme_certificate

    @accepts(
        Dict(
            'certificate_create',
            Bool('tos'),
            Dict('dns_mapping', additional_attrs=True),
            Int('csr_id'),
            Int('signedby'),
            Int('key_length', enum=[1024, 2048, 4096]),
            Int('renew_days'),
            Int('type'),
            Int('lifetime'),
            Int('serial', validators=[Range(min=1)]),
            Str('acme_directory_uri'),
            Str('certificate', max_length=None),
            Str('city'),
            Str('common', max_length=None, null=True),
            Str('country'),
            Str('CSR', max_length=None),
            Str('ec_curve', enum=CryptoKeyService.ec_curves, default=CryptoKeyService.ec_curve_default),
            Str('email', validators=[Email()]),
            Str('key_type', enum=['RSA', 'EC'], default='RSA'),
            Str('name', required=True),
            Str('organization'),
            Str('organizational_unit'),
            Str('passphrase'),
            Str('privatekey', max_length=None),
            Str('state'),
            Str('create_type', enum=[
                'CERTIFICATE_CREATE_INTERNAL', 'CERTIFICATE_CREATE_IMPORTED',
                'CERTIFICATE_CREATE_CSR', 'CERTIFICATE_CREATE_IMPORTED_CSR',
                'CERTIFICATE_CREATE_ACME'], required=True),
            Str('digest_algorithm', enum=['SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512']),
            List('san', items=[Str('san')]),
            Ref('cert_extensions'),
            register=True
        )
    )
    @job(lock='cert_create')
    async def do_create(self, job, data):
        """
        Create a new Certificate

        Certificates are classified under following types and the necessary keywords to be passed
        for `create_type` attribute to create the respective type of certificate

        1) Internal Certificate                 -  CERTIFICATE_CREATE_INTERNAL

        2) Imported Certificate                 -  CERTIFICATE_CREATE_IMPORTED

        3) Certificate Signing Request          -  CERTIFICATE_CREATE_CSR

        4) Imported Certificate Signing Request -  CERTIFICATE_CREATE_IMPORTED_CSR

        5) ACME Certificate                     -  CERTIFICATE_CREATE_ACME

        By default, created certs use RSA keys. If an Elliptic Curve Key is desired, it can be specified with the
        `key_type` attribute. If the `ec_curve` attribute is not specified for the Elliptic Curve Key, then default to
        using "BrainpoolP384R1" curve.

        A type is selected by the Certificate Service based on `create_type`. The rest of the values in `data` are
        validated accordingly and finally a certificate is made based on the selected type.

        `cert_extensions` can be specified to set X509v3 extensions.

        .. examples(websocket)::

          Create an ACME based certificate

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificate.create",
                "params": [{
                    "tos": true,
                    "csr_id": 1,
                    "acme_directory_uri": "https://acme-staging-v02.api.letsencrypt.org/directory",
                    "name": "acme_certificate",
                    "dns_mapping": {
                        "domain1.com": "1"
                    },
                    "create_type": "CERTIFICATE_CREATE_ACME"
                }]
            }

          Create an Imported Certificate Signing Request

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificate.create",
                "params": [{
                    "name": "csr",
                    "CSR": "CSR string",
                    "privatekey": "Private key string",
                    "create_type": "CERTIFICATE_CREATE_IMPORTED_CSR"
                }]
            }

          Create an Internal Certificate

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificate.create",
                "params": [{
                    "name": "internal_cert",
                    "key_length": 2048,
                    "lifetime": 3600,
                    "city": "Nashville",
                    "common": "domain1.com",
                    "country": "US",
                    "email": "dev@ixsystems.com",
                    "organization": "iXsystems",
                    "state": "Tennessee",
                    "digest_algorithm": "SHA256",
                    "signedby": 4,
                    "create_type": "CERTIFICATE_CREATE_INTERNAL"
                }]
            }
        """
        if not data.get('dns_mapping'):
            data.pop('dns_mapping')  # Default dict added

        create_type = data.pop('create_type')
        if create_type in (
            'CERTIFICATE_CREATE_IMPORTED_CSR', 'CERTIFICATE_CREATE_ACME', 'CERTIFICATE_CREATE_IMPORTED'
        ):
            for key in ('key_length', 'key_type', 'ec_curve'):
                data.pop(key, None)

        verrors = await self.validate_common_attributes(data, 'certificate_create')

        await validate_cert_name(
            self.middleware, data['name'], self._config.datastore,
            verrors, 'certificate_create.name'
        )

        if verrors:
            raise verrors

        job.set_progress(10, 'Initial validation complete')

        if create_type in (
            'CERTIFICATE_CREATE_IMPORTED_CSR',
            'CERTIFICATE_CREATE_ACME',
            'CERTIFICATE_CREATE_IMPORTED',
        ):
            # We add dictionaries/lists by default, so we need to explicitly remove them
            data.pop('cert_extensions')
            data.pop('san')

        if create_type == 'CERTIFICATE_CREATE_ACME':
            data = await self.middleware.run_in_thread(
                self.map_functions[create_type],
                job, data
            )
        else:
            data = await self.map_functions[create_type](job, data)

        data = {
            k: v for k, v in data.items()
            if k in [
                'name', 'certificate', 'CSR', 'privatekey', 'type', 'signedby', 'acme', 'acme_uri',
                'domains_authenticators', 'renew_days'
            ]
        }

        pk = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.start', 'ssl')

        job.set_progress(100, 'Certificate created successfully')

        return await self._get_instance(pk)

    @accepts(
        Dict(
            'acme_create',
            Bool('tos', default=False),
            Int('csr_id', required=True),
            Int('renew_days', default=10, validators=[Range(min=1)]),
            Str('acme_directory_uri', required=True),
            Str('name', required=True),
            Dict('dns_mapping', additional_attrs=True, required=True)
        )
    )
    @skip_arg(count=1)
    def __create_acme_certificate(self, job, data):

        csr_data = self.middleware.call_sync(
            'certificate.get_instance', data['csr_id']
        )
        verrors = ValidationErrors()
        email = (self.middleware.call_sync('user.query', [['uid', '=', 0]]))[0]['email']
        if not email:
            verrors.add(
                'name', 'Please configure an email address for "root" user which will be used with the ACME Server.'
            )
        verrors.check()

        data['acme_directory_uri'] += '/' if data['acme_directory_uri'][-1] != '/' else ''

        final_order = self.middleware.call_sync('acme.issue_certificate', job, 25, data, csr_data)

        job.set_progress(95, 'Final order received from ACME server')

        cert_dict = {
            'acme': self.middleware.call_sync(
                'acme.registration.query',
                [['directory', '=', data['acme_directory_uri']]]
            )[0]['id'],
            'acme_uri': final_order.uri,
            'certificate': final_order.fullchain_pem,
            'CSR': csr_data['CSR'],
            'privatekey': csr_data['privatekey'],
            'name': data['name'],
            'type': CERT_TYPE_EXISTING,
            'domains_authenticators': data['dns_mapping'],
            'renew_days': data['renew_days']
        }

        return cert_dict

    @accepts(
        Patch(
            'certificate_create_internal', 'certificate_create_csr',
            ('rm', {'name': 'signedby'}),
            ('rm', {'name': 'lifetime'})
        )
    )
    @private
    @skip_arg(count=1)
    async def create_csr(self, job, data):
        # no signedby, lifetime attributes required
        cert_info = get_cert_info_from_data(data)
        cert_info['cert_extensions'] = data['cert_extensions']

        data['type'] = CERT_TYPE_CSR

        req, key = await self.middleware.call(
            'cryptokey.generate_certificate_signing_request',
            cert_info
        )

        job.set_progress(80)

        data['CSR'] = req
        data['privatekey'] = key

        job.set_progress(90, 'Finalizing changes')

        return data

    @accepts(
        Dict(
            'create_imported_csr',
            Str('CSR', required=True, max_length=None, empty=False),
            Str('name'),
            Str('privatekey', required=True, max_length=None, empty=False),
            Str('passphrase')
        )
    )
    @skip_arg(count=1)
    async def __create_imported_csr(self, job, data):

        # TODO: We should validate csr with private key ?

        data['type'] = CERT_TYPE_CSR

        job.set_progress(80)

        if 'passphrase' in data:
            data['privatekey'] = await self.middleware.call(
                'cryptokey.export_private_key',
                data['privatekey'],
                data['passphrase']
            )

        job.set_progress(90, 'Finalizing changes')

        return data

    @accepts(
        Dict(
            'certificate_create_imported',
            Int('csr_id'),
            Str('certificate', required=True, max_length=None),
            Str('name'),
            Str('passphrase'),
            Str('privatekey', max_length=None)
        )
    )
    @skip_arg(count=1)
    async def __create_imported_certificate(self, job, data):
        verrors = ValidationErrors()

        csr_id = data.pop('csr_id', None)
        if csr_id:
            csr_obj = await self.query(
                [
                    ['id', '=', csr_id],
                    ['type', '=', CERT_TYPE_CSR]
                ],
                {'get': True}
            )

            data['privatekey'] = csr_obj['privatekey']
            data.pop('passphrase', None)
        elif not data.get('privatekey'):
            verrors.add(
                'certificate_create.privatekey',
                'Private key is required when importing a certificate'
            )

        if verrors:
            raise verrors

        job.set_progress(50, 'Validation complete')

        data['type'] = CERT_TYPE_EXISTING

        if 'passphrase' in data:
            data['privatekey'] = await self.middleware.call(
                'cryptokey.export_private_key',
                data['privatekey'],
                data['passphrase']
            )

        return data

    @accepts(
        Patch(
            'certificate_create', 'certificate_create_internal',
            ('edit', _set_required('lifetime')),
            ('edit', _set_required('country')),
            ('edit', _set_required('state')),
            ('edit', _set_required('city')),
            ('edit', _set_required('organization')),
            ('edit', _set_required('email')),
            ('edit', _set_required('san')),
            ('edit', _set_required('signedby')),
            ('rm', {'name': 'create_type'}),
            register=True
        )
    )
    @private
    @skip_arg(count=1)
    async def create_internal(self, job, data):

        cert_info = get_cert_info_from_data(data)
        data['type'] = CERT_TYPE_INTERNAL

        signing_cert = await self.middleware.call(
            'certificateauthority.query',
            [('id', '=', data['signedby'])],
            {'get': True}
        )

        cert_serial = await self.middleware.call(
            'certificateauthority.get_serial_for_certificate',
            data['signedby']
        )

        cert_info.update({
            'ca_privatekey': signing_cert['privatekey'],
            'ca_certificate': signing_cert['certificate'],
            'serial': cert_serial,
            'cert_extensions': data['cert_extensions']
        })

        cert, key = await self.middleware.call(
            'cryptokey.generate_certificate',
            cert_info
        )

        data['certificate'] = cert
        data['privatekey'] = key

        job.set_progress(90, 'Finalizing changes')

        return data

    @accepts(
        Int('id', required=True),
        Dict(
            'certificate_update',
            Bool('revoked'),
            Str('name')
        )
    )
    @job(lock='cert_update')
    async def do_update(self, job, id, data):
        """
        Update certificate of `id`

        Only name and revoked attribute can be updated.

        When `revoked` is enabled, the specified cert `id` is revoked and if it belongs to a CA chain which
        exists on this system, its serial number is added to the CA's certificate revocation list.

        .. examples(websocket)::

          Update a certificate of `id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificate.update",
                "params": [
                    1,
                    {
                        "name": "updated_name"
                    }
                ]
            }
        """
        old = await self._get_instance(id)
        # signedby is changed back to integer from a dict
        old['signedby'] = old['signedby']['id'] if old.get('signedby') else None
        if old.get('acme'):
            old['acme'] = old['acme']['id']

        new = old.copy()

        new.update(data)

        if any(new[k] != old[k] for k in ('name', 'revoked')):

            verrors = ValidationErrors()

            if new['name'] != old['name']:
                await validate_cert_name(
                    self.middleware, new['name'], self._config.datastore,
                    verrors, 'certificate_update.name'
                )

            if new['revoked'] and new['cert_type_CSR']:
                verrors.add(
                    'certificate_update.revoked',
                    'A CSR cannot be marked as revoked.'
                )
            elif new['revoked'] and not old['revoked'] and not new['can_be_revoked']:
                verrors.add(
                    'certificate_update.revoked',
                    'Only certificate(s) can be revoked which have a CA present on the system'
                )
            elif old['revoked'] and not new['revoked']:
                verrors.add(
                    'certificate_update.revoked',
                    'Certificate has already been revoked and this cannot be reversed'
                )

            verrors.check()

            if old['revoked'] != new['revoked'] and new['revoked']:
                revoked = {'revoked_date': datetime.datetime.utcnow()}
            else:
                revoked = {}

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                {'name': new['name'], **revoked},
                {'prefix': self._config.datastore_prefix}
            )

            await self.middleware.call('service.start', 'ssl')

        job.set_progress(90, 'Finalizing changes')

        return await self._get_instance(id)

    @private
    async def delete_domains_authenticator(self, auth_id):
        # Delete provided auth_id from all ACME based certs domains_authenticators
        for cert in await self.query([['acme', '!=', None]]):
            if auth_id in cert['domains_authenticators'].values():
                await self.middleware.call(
                    'datastore.update',
                    self._config.datastore,
                    cert['id'],
                    {
                        'domains_authenticators': {
                            k: v for k, v in cert['domains_authenticators'].items()
                            if v != auth_id
                        }
                    },
                    {'prefix': self._config.datastore_prefix}
                )

    @accepts(
        Int('id'),
        Bool('force', default=False)
    )
    @job(lock='cert_delete')
    def do_delete(self, job, id, force):
        """
        Delete certificate of `id`.

        If the certificate is an ACME based certificate, certificate service will try to
        revoke the certificate by updating it's status with the ACME server, if it fails an exception is raised
        and the certificate is not deleted from the system. However, if `force` is set to True, certificate is deleted
        from the system even if some error occurred while revoking the certificate with the ACME Server

        .. examples(websocket)::

          Delete certificate of `id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificate.delete",
                "params": [
                    1,
                    true
                ]
            }
        """
        check_dependencies(self.middleware, 'CERT', id)

        certificate = self.middleware.call_sync('certificate.get_instance', id)

        if certificate.get('acme'):
            client, key = self.middleware.call_sync(
                'acme.get_acme_client_and_key', certificate['acme']['directory'], True
            )

            try:
                client.revoke(
                    jose.ComparableX509(
                        crypto.load_certificate(crypto.FILETYPE_PEM, certificate['certificate'])
                    ),
                    0
                )
            except (errors.ClientError, messages.Error) as e:
                if not force:
                    raise CallError(f'Failed to revoke certificate: {e}')

        response = self.middleware.call_sync(
            'datastore.delete',
            self._config.datastore,
            id
        )

        self.middleware.call_sync('service.start', 'ssl')

        job.set_progress(100)
        return response


class CertificateAuthorityModel(sa.Model):
    __tablename__ = 'system_certificateauthority'

    id = sa.Column(sa.Integer(), primary_key=True)
    cert_type = sa.Column(sa.Integer())
    cert_name = sa.Column(sa.String(120), unique=True)
    cert_certificate = sa.Column(sa.Text(), nullable=True)
    cert_privatekey = sa.Column(sa.EncryptedText(), nullable=True)
    cert_CSR = sa.Column(sa.Text(), nullable=True)
    cert_revoked_date = sa.Column(sa.DateTime(), nullable=True)
    cert_signedby_id = sa.Column(sa.ForeignKey('system_certificateauthority.id'), index=True, nullable=True)


def get_ca_result_entry():
    entry = copy.deepcopy(CertificateService.ENTRY)
    entry.name = 'certificateauthority_entry'
    return entry


class CertificateAuthorityService(CRUDService):

    class Config:
        datastore = 'system.certificateauthority'
        datastore_extend = 'certificate.cert_extend'
        datastore_prefix = 'cert_'
        cli_namespace = 'system.certificate.authority'

    ENTRY = get_ca_result_entry()

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
            'lifetime': NOT_VALID_AFTER_DEFAULT,
            'digest_algorithm': 'SHA256'
        },
        'CA': {
            'key_length': 2048,
            'key_type': 'RSA',
            'lifetime': NOT_VALID_AFTER_DEFAULT,
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_create_functions = {
            'CA_CREATE_INTERNAL': self.__create_internal,
            'CA_CREATE_IMPORTED': self.__create_imported_ca,
            'CA_CREATE_INTERMEDIATE': self.__create_intermediate_ca,
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

    @periodic(86400, run_on_start=True)
    @private
    async def crl_generation(self):
        await self.middleware.call('service.start', 'ssl')

    # HELPER METHODS

    @private
    async def revoke_ca_chain(self, ca_id):
        chain = await self.get_ca_chain(ca_id)
        for cert in chain:
            datastore = f'system.certificate{"authority" if cert["cert_type"] == "CA" else ""}'
            await self.middleware.call(
                'datastore.update',
                datastore,
                cert['id'], {
                    'revoked_date': datetime.datetime.utcnow()
                },
                {'prefix': self._config.datastore_prefix}
            )

    @private
    async def get_ca_chain(self, ca_id):
        certs = list(
            map(
                lambda item: dict(item, cert_type='CERTIFICATE'),
                await self.middleware.call(
                    'datastore.query',
                    'system.certificate',
                    [['signedby', '=', ca_id]],
                    {'prefix': self._config.datastore_prefix}
                )
            )
        )

        for ca in await self.middleware.call(
            'datastore.query',
            'system.certificateauthority',
            [['signedby', '=', ca_id]],
            {'prefix': self._config.datastore_prefix}
        ):
            certs.extend((await self.get_ca_chain(ca['id'])))

        ca = await self.middleware.call(
            'datastore.query',
            'system.certificateauthority',
            [['id', '=', ca_id]],
            {'prefix': self._config.datastore_prefix, 'get': True}
        )
        ca.update({'cert_type': 'CA'})

        certs.append(ca)
        return certs

    @private
    async def validate_common_attributes(self, data, schema_name):
        verrors = ValidationErrors()

        await _validate_common_attributes(self.middleware, data, verrors, schema_name)

        if not data['cert_extensions']['BasicConstraints']['enabled']:
            verrors.add(
                f'{schema_name}.cert_extensions.BasicConstraints.enabled',
                'This must be enabled for a Certificate Authority.'
            )
        elif not data['cert_extensions']['BasicConstraints']['ca']:
            verrors.add(
                f'{schema_name}.cert_extensions.BasicConstraints.ca',
                '"ca" must be enabled for a Certificate Authority.'
            )

        if not data['cert_extensions']['KeyUsage']['enabled']:
            verrors.add(
                f'{schema_name}.cert_extensions.KeyUsage.enabled',
                'This must be enabled for a Certificate Authority.'
            )
        elif not data['cert_extensions']['KeyUsage']['key_cert_sign']:
            verrors.add(
                f'{schema_name}.cert_extensions.KeyUsage.key_cert_sign',
                '"key_cert_sign" must be enabled for a Certificate Authority.'
            )

        return verrors

    @private
    async def get_serial_for_certificate(self, ca_id):

        ca_data = await self._get_instance(ca_id)

        if ca_data.get('signedby'):
            # Recursively call the same function for it's parent and let the function gather all serials in a chain
            return await self.get_serial_for_certificate(ca_data['signedby']['id'])
        else:

            async def cert_serials(ca_id):
                return [
                    data['serial'] for data in
                    await self.middleware.call(
                        'datastore.query',
                        'system.certificate',
                        [('signedby', '=', ca_id)],
                        {
                            'prefix': self._config.datastore_prefix,
                            'extend': self._config.datastore_extend
                        }
                    )
                ]

            ca_signed_certs = await cert_serials(ca_id)

            async def child_serials(ca_id):
                serials = []
                children = await self.middleware.call(
                    'datastore.query',
                    self._config.datastore,
                    [('signedby', '=', ca_id)],
                    {
                        'prefix': self._config.datastore_prefix,
                        'extend': self._config.datastore_extend
                    }
                )

                for child in children:
                    serials.extend((await child_serials(child['id'])))

                serials.extend((await cert_serials(ca_id)))
                serials.append((await self._get_instance(ca_id))['serial'])

                return serials

            ca_signed_certs.extend((await child_serials(ca_id)))

            # This is for a case where the user might have a malformed certificate and serial value returns None
            ca_signed_certs = list(filter(None, ca_signed_certs))

            if not ca_signed_certs:
                return int(
                    (await self._get_instance(ca_id))['serial'] or 0
                ) + 1
            else:
                return max(ca_signed_certs) + 1

    def _set_enum(name):
        def set_enum(attr):
            attr.enum = ['CA_CREATE_INTERNAL', 'CA_CREATE_IMPORTED', 'CA_CREATE_INTERMEDIATE']
        return {'name': name, 'method': set_enum}

    def _set_cert_extensions_defaults(name):
        def set_defaults(attr):
            for ext, keys, values in (
                ('BasicConstraints', ('enabled', 'ca', 'extension_critical'), [True] * 3),
                ('KeyUsage', ('enabled', 'key_cert_sign', 'crl_sign', 'extension_critical'), [True] * 4),
                ('ExtendedKeyUsage', ('enabled', 'usages'), (True, ['SERVER_AUTH']))
            ):
                for k, v in zip(keys, values):
                    attr.attrs[ext].attrs[k].default = v

        return {'name': name, 'method': set_defaults}

    # CREATE METHODS FOR CREATING CERTIFICATE AUTHORITIES
    # "do_create" IS CALLED FIRST AND THEN BASED ON THE TYPE OF CA WHICH IS TO BE CREATED, THE
    # APPROPRIATE METHOD IS CALLED
    # FOLLOWING TYPES ARE SUPPORTED
    # CREATE_TYPE ( STRING )      - METHOD CALLED
    # CA_CREATE_INTERNAL          - __create_internal
    # CA_CREATE_IMPORTED          - __create_imported_ca
    # CA_CREATE_INTERMEDIATE      - __create_intermediate_ca

    @accepts(
        Patch(
            'certificate_create', 'ca_create',
            ('edit', _set_enum('create_type')),
            ('edit', _set_cert_extensions_defaults('cert_extensions')),
            ('rm', {'name': 'dns_mapping'}),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a new Certificate Authority

        Certificate Authorities are classified under following types with the necessary keywords to be passed
        for `create_type` attribute to create the respective type of certificate authority

        1) Internal Certificate Authority       -  CA_CREATE_INTERNAL

        2) Imported Certificate Authority       -  CA_CREATE_IMPORTED

        3) Intermediate Certificate Authority   -  CA_CREATE_INTERMEDIATE

        Created certificate authorities use RSA keys by default. If an Elliptic Curve Key is desired, then it can be
        specified with the `key_type` attribute. If the `ec_curve` attribute is not specified for the Elliptic
        Curve Key, default to using "BrainpoolP384R1" curve.

        A type is selected by the Certificate Authority Service based on `create_type`. The rest of the values
        are validated accordingly and finally a certificate is made based on the selected type.

        `cert_extensions` can be specified to set X509v3 extensions.

        .. examples(websocket)::

          Create an Internal Certificate Authority

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificateauthority.create",
                "params": [{
                    "name": "internal_ca",
                    "key_length": 2048,
                    "lifetime": 3600,
                    "city": "Nashville",
                    "common": "domain1.com",
                    "country": "US",
                    "email": "dev@ixsystems.com",
                    "organization": "iXsystems",
                    "state": "Tennessee",
                    "digest_algorithm": "SHA256"
                    "create_type": "CA_CREATE_INTERNAL"
                }]
            }

          Create an Imported Certificate Authority

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificateauthority.create",
                "params": [{
                    "name": "imported_ca",
                    "certificate": "Certificate string",
                    "privatekey": "Private key string",
                    "create_type": "CA_CREATE_IMPORTED"
                }]
            }
        """
        create_type = data.pop('create_type')
        if create_type == 'CA_CREATE_IMPORTED':
            for key in ('key_length', 'key_type', 'ec_curve'):
                data.pop(key, None)

        verrors = await self.validate_common_attributes(data, 'certificate_authority_create')

        await validate_cert_name(
            self.middleware, data['name'], self._config.datastore,
            verrors, 'certificate_authority_create.name'
        )

        if verrors:
            raise verrors

        data = await self.map_create_functions[create_type](data)

        data = {
            k: v for k, v in data.items()
            if k in ['name', 'certificate', 'privatekey', 'type', 'signedby']
        }

        pk = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.start', 'ssl')

        return await self._get_instance(pk)

    @accepts(
        Dict(
            'ca_sign_csr',
            Int('ca_id', required=True),
            Int('csr_cert_id', required=True),
            Str('name', required=True),
            Ref('cert_extensions'),
            register=True
        )
    )
    @returns(Ref('certificate_entry'))
    async def ca_sign_csr(self, data):
        """
        Sign CSR by Certificate Authority of `ca_id`

        Sign CSR's and generate a certificate from it. `ca_id` provides which CA is to be used for signing
        a CSR of `csr_cert_id` which exists in the system

        `cert_extensions` can be specified if specific extensions are to be set in the newly signed certificate.

        .. examples(websocket)::

          Sign CSR of `csr_cert_id` by Certificate Authority of `ca_id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificateauthority.ca_sign_csr",
                "params": [{
                    "ca_id": 1,
                    "csr_cert_id": 1,
                    "name": "signed_cert"
                }]
            }
        """
        return await self.__ca_sign_csr(data)

    @accepts(
        Ref('ca_sign_csr'),
        Str('schema_name', default='certificate_authority_update')
    )
    async def __ca_sign_csr(self, data, schema_name):
        verrors = ValidationErrors()

        ca_data = await self.query([('id', '=', data['ca_id'])])
        csr_cert_data = await self.middleware.call('certificate.query', [('id', '=', data['csr_cert_id'])])

        if not ca_data:
            verrors.add(
                f'{schema_name}.ca_id',
                f'No Certificate Authority found for id {data["ca_id"]}'
            )
        else:
            ca_data = ca_data[0]
            if not ca_data.get('privatekey'):
                verrors.add(
                    f'{schema_name}.ca_id',
                    'Please use a CA which has a private key assigned'
                )

        if not csr_cert_data:
            verrors.add(
                f'{schema_name}.csr_cert_id',
                f'No Certificate found for id {data["csr_cert_id"]}'
            )
        else:
            csr_cert_data = csr_cert_data[0]
            if not csr_cert_data.get('CSR'):
                verrors.add(
                    f'{schema_name}.csr_cert_id',
                    'No CSR has been filed by this certificate'
                )
            else:
                if not await self.middleware.call('cryptokey.load_certificate_request', csr_cert_data['CSR']):
                    verrors.add(
                        f'{schema_name}.csr_cert_id',
                        'CSR not valid'
                    )
                if not csr_cert_data['privatekey']:
                    verrors.add(
                        f'{schema_name}.csr_cert_id',
                        'Private key not found for specified CSR.'
                    )

        if verrors:
            raise verrors

        serial = await self.get_serial_for_certificate(ca_data['id'])

        new_cert = await self.middleware.call(
            'cryptokey.sign_csr_with_ca',
            {
                'ca_certificate': ca_data['certificate'],
                'ca_privatekey': ca_data['privatekey'],
                'csr': csr_cert_data['CSR'],
                'csr_privatekey': csr_cert_data['privatekey'],
                'serial': serial,
                'digest_algorithm': ca_data['digest_algorithm'],
                'cert_extensions': data['cert_extensions']
            }
        )

        new_csr = {
            'type': CERT_TYPE_INTERNAL,
            'name': data['name'],
            'certificate': new_cert,
            'privatekey': csr_cert_data['privatekey'],
            'signedby': ca_data['id']
        }

        new_csr_id = await self.middleware.call(
            'datastore.insert',
            'system.certificate',
            new_csr,
            {'prefix': 'cert_'}
        )

        await self.middleware.call('service.start', 'ssl')

        return await self.middleware.call(
            'certificate.query',
            [['id', '=', new_csr_id]],
            {'get': True}
        )

    @accepts(
        Patch(
            'ca_create_internal', 'ca_create_intermediate',
            ('add', {'name': 'signedby', 'type': 'int', 'required': True}),
        ),
    )
    async def __create_intermediate_ca(self, data):

        signing_cert = await self._get_instance(data['signedby'])

        serial = await self.get_serial_for_certificate(signing_cert['id'])

        data['type'] = CA_TYPE_INTERMEDIATE

        cert_info = get_cert_info_from_data(data)
        cert_info.update({
            'ca_privatekey': signing_cert['privatekey'],
            'ca_certificate': signing_cert['certificate'],
            'serial': serial,
            'cert_extensions': data['cert_extensions']
        })

        cert, key = await self.middleware.call(
            'cryptokey.generate_certificate_authority',
            cert_info
        )

        data['certificate'] = cert
        data['privatekey'] = key

        return data

    @accepts(
        Patch(
            'ca_create', 'ca_create_imported',
            ('edit', _set_required('certificate')),
            ('rm', {'name': 'create_type'}),
        )
    )
    async def __create_imported_ca(self, data):
        data['type'] = CA_TYPE_EXISTING

        if all(k in data for k in ('passphrase', 'privatekey')):
            data['privatekey'] = await self.middleware.call(
                'cryptokey.export_private_key',
                data['privatekey'],
                data['passphrase']
            )

        return data

    @accepts(
        Patch(
            'ca_create', 'ca_create_internal',
            ('edit', _set_required('lifetime')),
            ('edit', _set_required('country')),
            ('edit', _set_required('state')),
            ('edit', _set_required('city')),
            ('edit', _set_required('organization')),
            ('edit', _set_required('email')),
            ('edit', _set_required('san')),
            ('rm', {'name': 'create_type'}),
            register=True
        )
    )
    async def __create_internal(self, data):
        cert_info = get_cert_info_from_data(data)
        cert_info['serial'] = random.getrandbits(24)

        cert_info['cert_extensions'] = data['cert_extensions']
        (cert, key) = await self.middleware.call(
            'cryptokey.generate_self_signed_ca',
            cert_info
        )

        data['type'] = CA_TYPE_INTERNAL
        data['certificate'] = cert
        data['privatekey'] = key

        return data

    @accepts(
        Int('id', required=True),
        Dict(
            'ca_update',
            Bool('revoked'),
            Int('ca_id'),
            Int('csr_cert_id'),
            Str('create_type', enum=['CA_SIGN_CSR']),
            Str('name'),
        )
    )
    async def do_update(self, id, data):
        """
        Update Certificate Authority of `id`

        Only `name` and `revoked` attribute can be updated.

        If `revoked` is enabled, the CA and its complete chain is marked as revoked and added to the CA's
        certificate revocation list.

        .. examples(websocket)::

          Update a Certificate Authority of `id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificateauthority.update",
                "params": [
                    1,
                    {
                        "name": "updated_ca_name"
                    }
                ]
            }
        """
        if data.pop('create_type', '') == 'CA_SIGN_CSR':
            # BEING USED BY OLD LEGACY FOR SIGNING CSR'S. THIS CAN BE REMOVED WHEN LEGACY UI IS REMOVED
            data['ca_id'] = id
            return await self.__ca_sign_csr(data, 'certificate_authority_update')
        else:
            for key in ['ca_id', 'csr_cert_id']:
                data.pop(key, None)

        old = await self._get_instance(id)
        # signedby is changed back to integer from a dict
        old['signedby'] = old['signedby']['id'] if old.get('signedby') else None

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if any(new[k] != old[k] for k in ('name', 'revoked')):
            if new['name'] != old['name']:
                await validate_cert_name(
                    self.middleware, new['name'], self._config.datastore,
                    verrors, 'certificate_authority_update.name'
                )

            if old['revoked'] != new['revoked'] and new['revoked'] and not new['privatekey']:
                verrors.add(
                    'certificate_authority_update.revoked',
                    'Only Certificate Authorities with a privatekey can be marked as revoked.'
                )
            elif old['revoked'] and not new['revoked']:
                verrors.add(
                    'certificate_authority_update.revoked',
                    'Certificate Authority has already been revoked and this cannot be reversed'
                )

            if verrors:
                raise verrors

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                {'name': new['name']},
                {'prefix': self._config.datastore_prefix}
            )

            if old['revoked'] != new['revoked'] and new['revoked']:
                await self.revoke_ca_chain(id)

            await self.middleware.call('service.start', 'ssl')

        return await self._get_instance(id)

    async def do_delete(self, id):
        """
        Delete a Certificate Authority of `id`

        .. examples(websocket)::

          Delete a Certificate Authority of `id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificateauthority.delete",
                "params": [
                    1
                ]
            }
        """
        await self._get_instance(id)
        await self.middleware.run_in_thread(check_dependencies, self.middleware, 'CA', id)

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call('service.start', 'ssl')

        return response


async def setup(middlewared):
    failure = False
    try:
        system_general_config = await middlewared.call('system.general.config')
        system_cert = system_general_config['ui_certificate']
        certs = await middlewared.call('certificate.query')
    except Exception as e:
        failure = True
        middlewared.logger.error(f'Failed to retrieve certificates: {e}', exc_info=True)

    if not failure and (not system_cert or system_cert['id'] not in [c['id'] for c in certs]):
        # create a self signed cert if it doesn't exist and set ui_certificate to it's value
        try:
            if not any('freenas_default' == c['name'] for c in certs):
                cert, key = await middlewared.call('cryptokey.generate_self_signed_certificate')

                cert_dict = {
                    'certificate': cert,
                    'privatekey': key,
                    'name': 'freenas_default',
                    'type': CERT_TYPE_EXISTING,
                }

                # We use datastore.insert to directly insert in db as jobs cannot be waited for at this point
                id = await middlewared.call(
                    'datastore.insert',
                    'system.certificate',
                    cert_dict,
                    {'prefix': 'cert_'}
                )

                await middlewared.call('service.start', 'ssl')

                middlewared.logger.debug('Default certificate for System created')
            else:
                id = [c['id'] for c in certs if c['name'] == 'freenas_default'][0]
                await middlewared.call('certificate.cert_services_validation', id, 'certificate')

            await middlewared.call(
                'datastore.update', 'system.settings', system_general_config['id'], {'stg_guicertificate': id}
            )
        except Exception as e:
            failure = True
            middlewared.logger.debug(
                'Failed to set certificate for system.general plugin: %s', e, exc_info=True
            )

    if not failure:
        middlewared.logger.debug('Certificate setup for System complete')
