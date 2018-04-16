import dateutil
import dateutil.parser
import os
import random
import re

from middlewared.async_validators import validate_country
from middlewared.schema import accepts, Dict, Int, List, Patch, Ref, Str
from middlewared.service import CRUDService, filterable, private, ValidationErrors
from middlewared.validators import Email, IpAddress, ShouldBe
from OpenSSL import crypto, SSL


CA_TYPE_EXISTING = 0x01
CA_TYPE_INTERNAL = 0x02
CA_TYPE_INTERMEDIATE = 0x04
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_INTERNAL = 0x10
CERT_TYPE_CSR = 0x20

CERT_ROOT_PATH = '/etc/certificates'
CERT_CA_ROOT_PATH = '/etc/certificates/CA'
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)


def get_cert_info_from_data(data):
    cert_info_keys = ['key_length', 'country', 'state', 'city', 'organization', 'common',
                      'san', 'serial', 'email', 'lifetime', 'digest_algorithm']
    return {key: data.get(key) for key in cert_info_keys}


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
    #  FIXME: FOR CSR - SHOULD THE FOLLOWING CONDITION BE THERE ?
    if cert_name in ("external", "self-signed", "external - signature pending"):
        verrors.add(
            name,
            '{0} is a reserved internal keyword for Certificate Management'.format(cert_name)
        )
    reg = re.search(r'^[a-z0-9_\-]+$', cert_name or '', re.I)
    if not reg:
        verrors.add(
            name,
            'Use alphanumeric characters, "_" and "-".'
        )


async def validate_certificate_keys_match(middleware, public_key, private_key, verrors, name, passphrase=None):
    # CALLED ON THE ASSUMPTION THAT PUBLIC KEY, PRIVATE KEY ARE VALID

    public_key_obj = crypto.load_certificate(crypto.FILETYPE_PEM, public_key)
    private_key_obj = await middleware.call('certificate.load_private_key', private_key, passphrase)

    try:
        context = SSL.Context(SSL.TLSv1_2_METHOD)
        context.use_certificate(public_key_obj)
        context.use_privatekey(private_key_obj)
        context.check_privatekey()
    except SSL.Error as e:
        verrors.add(
            name,
            f'Private key does not match certificate: {e}'
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

        nmatches = len(matches)
        if not nmatches:
            verrors.add(
                f'{schema_name}.certificate',
                'Not a valid certificate'
            )
        else:
            cert_info = await middleware.call('certificate.load_certificate', certificate)
            if not cert_info:
                verrors.add(
                    f'{schema_name}.certificate',
                    'Certificate not in PEM format'
                )

    private_key = data.get('privatekey')
    passphrase = data.get('passphrase')
    passphrase2 = data.get('passphrase2')
    if private_key:
        if not (await middleware.call('certificate.load_private_key', private_key, passphrase)):
            verrors.add(
                f'{schema_name}.privatekey',
                'Please provide a valid private key with matching passphrase ( if any )'
            )
        elif passphrase != passphrase2:
            for f in ['passphrase', 'passphrase2']:
                verrors.add(
                    f'{schema_name}.{f}',
                    'Pass phrase confirmation does not match'
                )
    elif passphrase or passphrase2:
        verrors.add(
            f'{schema_name}.passphrase',
            'No private key specified for pass phrase'
        )

    if (
        (certificate and private_key) and
        all(k not in verrors for k in (f'{schema_name}.certificate', f'{schema_name}.privatekey'))
    ):
        await validate_certificate_keys_match(
            middleware, certificate, private_key,
            verrors, f'{schema_name}.privatekey',
            passphrase
        )

    key_length = data.get('key_length')
    if key_length:
        if key_length not in [1024, 2048, 4096]:
            verrors.add(
                f'{schema_name}.key_length',
                'Key length must be a valid value ( 1024, 2048, 4096 )'
            )

    signedby = data.get('signedby')
    if signedby:
        valid_signing_cas = await middleware.call(
            'certificateauthority.query',
            [
                ('certificate', '!=', None),
                ('privatekey', '!=', None),
                ('certificate', '!=', ''),
                ('privatekey', '!=', ''),
            ],
        )

        if signedby not in [d['id'] for d in valid_signing_cas]:
            verrors.add(
                f'{schema_name}.signedby',
                'Please provide a valid signing authority'
            )


class CertificateService(CRUDService):

    class Config:
        datastore = 'system.certificate'
        datastore_extend = 'certificate.cert_extend'
        datastore_prefix = 'cert_'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_functions = {
            'CERTIFICATE_CREATE_INTERNAL': self.__create_internal,
            'CERTIFICATE_CREATE_IMPORTED': self.__create_imported_certificate,
            'CERTIFICATE_CREATE': self.__create_certificate,
            'CERTIFICATE_CREATE_CSR': self.__create_csr
        }

    @filterable
    async def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['extend'] = self._config.datastore_extend
        options['prefix'] = self._config.datastore_prefix
        return await self.middleware.call('datastore.query', self._config.datastore, filters, options)

    @private
    async def cert_extend(self, cert):
        """Extend certificate with some useful attributes."""
        if cert.get('signedby'):
            cert['signedby'] = await self.middleware.call(
                'certificateauthority.query',
                [('id', '=', cert['signedby']['id'])],
                {'get': True}
            )

        # convert san to list
        cert['san'] = cert['san'].split() if cert['san'] else []

        if cert['type'] in (
                CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE
        ):
            root_path = CERT_CA_ROOT_PATH
        else:
            root_path = CERT_ROOT_PATH
        cert['root_path'] = root_path
        cert['certificate_path'] = os.path.join(
            root_path, '{0}.crt'.format(cert['name'])
        )
        cert['privatekey_path'] = os.path.join(
            root_path, '{0}.key'.format(cert['name'])
        )
        cert['csr_path'] = os.path.join(
            root_path, '{0}.csr'.format(cert['name'])
        )

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
        if cert['chain']:
            certs = RE_CERTIFICATE.findall(cert['certificate'])
        else:
            certs = [cert['certificate']]
            signing_CA = cert['issuer']
            # Recursively get all internal/intermediate certificates
            # FIXME: NONE HAS BEEN ADDED IN THE FOLLOWING CHECK FOR CSR'S WHICH HAVE BEEN SIGNED BY A CA
            while signing_CA not in ["external", "self-signed", "external - signature pending", None]:
                certs.append(signing_CA['certificate'])
                signing_CA['issuer'] = cert_issuer(signing_CA)
                signing_CA = signing_CA['issuer']

        cert_obj = None
        try:
            for c in certs:
                # XXX Why load certificate if we are going to dump it right after?
                # Maybe just to verify its integrity?
                # Logic copied from freenasUI
                cert_obj = crypto.load_certificate(crypto.FILETYPE_PEM, c)
                cert['chain_list'].append(
                    crypto.dump_certificate(crypto.FILETYPE_PEM, cert_obj).decode()
                )
        except Exception:
            self.logger.debug('Failed to load certificate {0}'.format(cert['name']), exc_info=True)

        try:
            if cert['privatekey']:
                key_obj = crypto.load_privatekey(crypto.FILETYPE_PEM, cert['privatekey'])
                cert['privatekey'] = crypto.dump_privatekey(crypto.FILETYPE_PEM, key_obj).decode()
        except Exception:
            self.logger.debug('Failed to load privatekey {0}'.format(cert['name']), exc_info=True)

        try:
            if cert['CSR']:
                csr_obj = crypto.load_certificate_request(crypto.FILETYPE_PEM, cert['CSR'])
                cert['CSR'] = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr_obj).decode()
        except Exception:
            self.logger.debug('Failed to load csr {0}'.format(cert['name']), exc_info=True)

        cert['internal'] = 'NO' if cert['type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING) else 'YES'

        obj = None
        # date not applicable for CSR
        cert['from'] = None
        cert['until'] = None
        if cert['type'] == CERT_TYPE_CSR:
            obj = csr_obj
        elif cert_obj:
            obj = cert_obj
            notBefore = obj.get_notBefore()
            t1 = dateutil.parser.parse(notBefore)
            t2 = t1.astimezone(dateutil.tz.tzutc())
            cert['from'] = t2.ctime()

            notAfter = obj.get_notAfter()
            t1 = dateutil.parser.parse(notAfter)
            t2 = t1.astimezone(dateutil.tz.tzutc())
            cert['until'] = t2.ctime()

        if obj:
            cert['DN'] = '/' + '/'.join([
                '%s=%s' % (c[0].decode(), c[1].decode())
                for c in obj.get_subject().get_components()
            ])

        return cert

    # HELPER METHODS

    @accepts(
        Str('certificate', required=True)
    )
    async def load_certificate(self, certificate):
        try:
            cert = crypto.load_certificate(
                crypto.FILETYPE_PEM,
                certificate
            )
        except crypto.Error:
            return {}
        else:
            cert_info = {
                'country': cert.get_subject().C,
                'state': cert.get_subject().ST,
                'city': cert.get_subject().L,
                'organization': cert.get_subject().O,
                'common': cert.get_subject().CN,
                'san': cert.get_subject().subjectAltName,
                'email': cert.get_subject().emailAddress,
            }

            signature_algorithm = cert.get_signature_algorithm().decode()
            m = re.match('^(.+)[Ww]ith', signature_algorithm)
            if m:
                cert_info['digest_algorithm'] = m.group(1).upper()

            return cert_info

    @accepts(
        Str('buffer', required=True),
        Str('passphrase', default=None)
    )
    async def export_private_key(self, buffer, passphrase):
        key = await self.load_private_key(buffer, passphrase)
        if key:
            return crypto.dump_privatekey(
                crypto.FILETYPE_PEM,
                key,
                passphrase=passphrase.encode() if passphrase else None
            ).decode()

    @accepts(
        Str('buffer', required=True),
        Str('passphrase', default=None)
    )
    async def load_private_key(self, buffer, passphrase):
        try:
            return crypto.load_privatekey(
                crypto.FILETYPE_PEM,
                buffer,
                passphrase=passphrase.encode() if passphrase else None
            )
        except crypto.Error:
            return None

    @accepts(
        Int('certificate_id', required=True)
    )
    async def get_fingerprint(self, certificate_id):
        certificate_list = await self.query(filters=[('id', '=', certificate_id)])
        if len(certificate_list) == 0:
            return None
        else:
            cert_certificate = certificate_list[0]['certificate']

        # getting fingerprint of certificate
        try:
            certificate = crypto.load_certificate(
                crypto.FILETYPE_PEM,
                cert_certificate
            )
        except Exception:
            return None
        else:
            return certificate.digest('sha1').decode()

    @accepts(
        Dict(
            'certificate_cert_info',
            Int('key_length'),
            Int('lifetime', required=True),
            Str('country', required=True),
            Str('state', required=True),
            Str('city', required=True),
            Str('organization', required=True),
            Str('common', required=True),
            Str('email', validators=[Email()], required=True),
            Str('serial', required=False),
            Str('digest_algorithm', enum=['SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512']),
            List('san', items=[Str('san')], default=[]),
            register=True
        )
    )
    async def create_certificate(self, cert_info):
        cert_info['san'] = ' '.join(cert_info['san'])

        cert = crypto.X509()
        cert.get_subject().C = cert_info['country']
        cert.get_subject().ST = cert_info['state']
        cert.get_subject().L = cert_info['city']
        cert.get_subject().O = cert_info['organization']
        cert.get_subject().CN = cert_info['common']
        # Add subject alternate name in addition to CN
        # first lets determine if an ip address was specified or
        # a dns entry in the common name
        default_san_type = 'DNS'
        try:
            ip_validator = IpAddress()
            ip_validator(cert_info['common'])
            default_san_type = 'IP'
        except ShouldBe:
            # This is raised if say we specified freenas.org in the Common name
            pass
        if cert_info['san']:
            cert.add_extensions([crypto.X509Extension(
                b"subjectAltName", False, f"{default_san_type}:{cert_info['san']}".encode()
            )])
            cert.get_subject().subjectAltName = cert_info['san'].replace(" ", ", ")
        cert.get_subject().emailAddress = cert_info['email']

        serial = cert_info.get('serial')
        if serial is not None:
            cert.set_serial_number(serial)

        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(cert_info['lifetime'] * (60 * 60 * 24))

        cert.set_issuer(cert.get_subject())
        # Setting it to '2' actually results in a v3 cert
        # openssl's cert x509 versions are zero-indexed!
        # see: https://www.ietf.org/rfc/rfc3280.txt
        cert.set_version(2)
        return cert

    @accepts(
        Patch(
            'certificate_cert_info', 'certificate_signing_request',
            ('rm', {'name': 'lifetime'})
        )
    )
    async def create_certificate_signing_request(self, cert_info):
        cert_info['san'] = ' '.join(cert_info['san'])

        key = await self.generate_key(cert_info['key_length'])

        req = crypto.X509Req()
        req.get_subject().C = cert_info['country']
        req.get_subject().ST = cert_info['state']
        req.get_subject().L = cert_info['city']
        req.get_subject().O = cert_info['organization']
        req.get_subject().CN = cert_info['common']
        # first lets determine if an ip address was specified or
        # a dns entry in the common name
        default_san_type = 'DNS'
        try:
            ip_validator = IpAddress()
            ip_validator(cert_info['common'])
            default_san_type = 'IP'
        except ShouldBe:
            # This is raised if say we specified freenas.org in the Common name
            pass
        if cert_info['san']:
            req.add_extensions(
                [crypto.X509Extension(b"subjectAltName", False, f"{default_san_type}:{cert_info['san']}".encode())])
            req.get_subject().subjectAltName = cert_info['san'].replace(" ", ", ")
        req.get_subject().emailAddress = cert_info['email']

        req.set_pubkey(key)
        req.sign(key, cert_info['digest_algorithm'])

        return (req, key)

    @private
    async def validate_common_attributes(self, data, schema_name):
        verrors = ValidationErrors()

        await _validate_common_attributes(self.middleware, data, verrors, schema_name)

        return verrors

    @accepts(
        Int('key_length')
    )
    async def generate_key(self, key_length):
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, key_length)
        return k

    # CREATE METHODS FOR CREATING CERTIFICATES
    # "do_create" IS CALLED FIRST AND THEN BASED ON THE TYPE OF THE CERTIFICATE WHICH IS TO BE CREATED THE
    # APPROPRIATE METHOD IS CALLED
    # FOLLOWING TYPES ARE SUPPORTED
    # CREATE_TYPE ( STRING )      - METHOD CALLED
    # CERTIFICATE_CREATE_INTERNAL - __create_internal
    # CERTIFICATE_CREATE_IMPORTED - __create_imported_certificate
    # CERTIFICATE_CREATE          - __create_certificate
    # CERTIFICATE_CREATE_CSR      - __create_csr

    @accepts(
        Dict(
            'certificate_create',
            Int('signedby'),
            Int('key_length'),
            Int('type'),
            Int('lifetime'),
            Int('serial'),
            Str('certificate'),
            Str('city'),
            Str('common'),
            Str('country'),
            Str('email', validators=[Email()]),
            Str('name', required=True),
            Str('organization'),
            Str('passphrase'),
            Str('passphrase2'),
            Str('privatekey'),
            Str('state'),
            Str('create_type', enum=[
                'CERTIFICATE_CREATE_INTERNAL', 'CERTIFICATE_CREATE_IMPORTED',
                'CERTIFICATE_CREATE', 'CERTIFICATE_CREATE_CSR'], required=True),
            Str('digest_algorithm', enum=['SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512']),
            List('san', items=[Str('san')], default=[]),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = await self.validate_common_attributes(data, 'certificate_create')

        await validate_cert_name(
            self.middleware, data['name'], self._config.datastore,
            verrors, 'certificate_create.name'
        )

        if verrors:
            raise verrors

        data = await self.map_functions[data.pop('create_type')](data)

        if 'san' in data:
            data['san'] = ' '.join(data['san']) if data.get('san') else ''

        pk = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call(
            'service.start',
            'ix-ssl',
            {'onetime': True}
        )

        return await self._get_instance(pk)

    @accepts(
        Patch(
            'certificate_create_internal', 'certificate_create_csr',
            ('rm', {'name': 'signedby'}),
            ('rm', {'name': 'lifetime'})
        )
    )
    async def __create_csr(self, data):
        # no signedby, lifetime attributes required
        cert_info = get_cert_info_from_data(data)
        cert_info.pop('lifetime')

        data['type'] = CERT_TYPE_CSR

        req, key = await self.create_certificate_signing_request(cert_info)

        data['CSR'] = crypto.dump_certificate_request(crypto.FILETYPE_PEM, req)
        data['privatekey'] = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)

        return data

    @accepts(
        Patch(
            'certificate_create', 'create_certificate',
            ('edit', _set_required('certificate')),
            ('edit', _set_required('privatekey')),
            ('edit', _set_required('type')),
            ('rm', {'name': 'create_type'})
        )
    )
    async def __create_certificate(self, data):

        for k, v in (await self.load_certificate(data['certificate'])).items():
            data[k] = v

        return data

    @accepts(
        Patch(
            'certificate_create', 'certificate_create_imported',
            ('edit', _set_required('certificate')),
            ('edit', _set_required('privatekey')),
            ('rm', {'name': 'create_type'})
        )
    )
    async def __create_imported_certificate(self, data):
        data['type'] = CERT_TYPE_EXISTING

        data = await self.__create_certificate(data)

        data['chain'] = True if len(RE_CERTIFICATE.findall(data['certificate'])) > 1 else False

        if 'passphrase' in data:
            private_key = await self.export_private_key(data['privatekey'], data['passphrase'])
            data['privatekey'] = private_key

        data.pop('passphrase', None)
        data.pop('passphrase2', None)

        return data

    @accepts(
        Patch(
            'certificate_create', 'certificate_create_internal',
            ('edit', _set_required('key_length')),
            ('edit', _set_required('digest_algorithm')),
            ('edit', _set_required('lifetime')),
            ('edit', _set_required('country')),
            ('edit', _set_required('state')),
            ('edit', _set_required('city')),
            ('edit', _set_required('organization')),
            ('edit', _set_required('email')),
            ('edit', _set_required('common')),
            ('edit', _set_required('signedby')),
            ('rm', {'name': 'create_type'}),
            register=True
        )
    )
    async def __create_internal(self, data):
        cert_info = get_cert_info_from_data(data)
        data['type'] = CERT_TYPE_INTERNAL

        signing_cert = await self.middleware.call(
            'certificateauthority.query',
            [('id', '=', data['signedby'])],
            {'get': True}
        )

        public_key = await self.generate_key(data['key_length'])
        signkey = await self.load_private_key(signing_cert['privatekey'])

        cert = await self.create_certificate(cert_info)
        cert.set_pubkey(public_key)
        cacert = crypto.load_certificate(crypto.FILETYPE_PEM, signing_cert['certificate'])
        cert.set_issuer(cacert.get_subject())
        cert.add_extensions([
            crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
        ])

        cert_serial = signing_cert['serial']
        if not cert_serial:
            cert_serial = 1

        cert.set_serial_number(cert_serial)
        cert.sign(signkey, data['digest_algorithm'])

        data['certificate'] = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        data['privatekey'] = crypto.dump_privatekey(crypto.FILETYPE_PEM, public_key)

        ca_cert_serial = signing_cert['serial']
        if not ca_cert_serial:
            ca_cert_serial = cert_serial

        await self.middleware.call(
            'certificateauthority.update',
            signing_cert['id'],
            {
                'serial': ca_cert_serial + 1,
                'start_ssl': False
            }
        )

        return data

    @accepts(
        Int('id', required=True),
        Patch('certificate_create', 'certificate_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        # TODO: SHOULD WE ALLOW END USER TO UPDATE ATTRIBUTES SUCH AS SIGNED BY?
        old = await self._get_instance(id)
        # signedby is changed back to integer from a dict
        old['signedby'] = old['signedby']['id'] if old.get('signedby') else None

        new = old.copy()

        new.update(data)

        verrors = await self.validate_common_attributes(new, 'certificate_update')

        if new['name'] != old['name']:
            await validate_cert_name(self.middleware, data['name'], self._config.datastore, verrors,
                                     'certificate_update.name')

        required_fields = ['certificate', 'privatekey', 'name']
        for field in required_fields:
            if not new.get(field):
                verrors.add(
                    f'certificate_update.{field}',
                    f'{field} is required'
                )

        if old['type'] == CERT_TYPE_CSR:
            if new['certificate']:
                # THE TYPE SHOULD ONLY BE CHANGED WHEN A CERTIFICATE HAS BEEN ADDED TO THE CSR ?
                # IN FREENASUI, THE TYPE WAS CHANGED REGARDLESS OF ANY UPDATE OF ANY ATTRIBUTE
                new['type'] = CERT_TYPE_EXISTING
                new['chain'] = True if len(RE_CERTIFICATE.findall(new['certificate'])) > 1 else False

        if verrors:
            raise verrors

        new['san'] = ' '.join(new['san']) if data.get('san') else ''

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call(
            'service.start',
            'ix-ssl',
            {'onetime': True}
        )

        return await self._get_instance(id)

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call(
            'service.start',
            'ix-ssl',
            {'onetime': True}
        )
        return response


class CertificateAuthorityService(CRUDService):

    class Config:
        datastore = 'system.certificateauthority'
        datastore_extend = 'certificate.cert_extend'
        datastore_prefix = 'cert_'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_create_functions = {
            'CA_CREATE_INTERNAL': self.__create_internal,
            'CA_CREATE_IMPORTED': self.__create_imported_ca,
            'CA_CREATE_INTERMEDIATE': self.__create_intermediate_ca,
        }

    @filterable
    async def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['extend'] = self._config.datastore_extend
        options['prefix'] = self._config.datastore_prefix
        return await self.middleware.call('datastore.query', self._config.datastore, filters, options)

    # HELPER METHODS

    @private
    async def validate_common_attributes(self, data, schema_name):
        verrors = ValidationErrors()

        await _validate_common_attributes(self.middleware, data, verrors, schema_name)

        return verrors

    @accepts(
        Ref('certificate_cert_info')
    )
    async def create_self_signed_CA(self, cert_info):
        key = await self.middleware.call('certificate.generate_key', cert_info['key_length'])
        cert = await self.middleware.call('certificate.create_certificate', cert_info)
        cert.set_pubkey(key)
        cert.add_extensions([
            crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE"),
            crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
            crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
        ])
        cert.set_serial_number(0o1)
        cert.sign(key, cert_info['digest_algorithm'])
        return (cert, key)

    def _set_enum(name):
        def set_enum(attr):
            attr.enum = ['CA_CREATE_INTERNAL', 'CA_CREATE_IMPORTED', 'CA_CREATE_INTERMEDIATE']
        return {'name': name, 'method': set_enum}

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
            ('add', {'type': 'int', 'name': 'csr_cert_id'}),
            ('add', {'type': 'int', 'name': 'ca_id'}),
            ('edit', _set_enum('create_type')),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = await self.validate_common_attributes(data, 'certificate_authority_create')

        await validate_cert_name(
            self.middleware, data['name'], self._config.datastore,
            verrors, 'certificate_authority_create.name'
        )

        if verrors:
            raise verrors

        data = await self.map_create_functions[data.pop('create_type')](data)

        data['san'] = ' '.join(data['san']) if data.get('san') else ''

        pk = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call(
            'service.start',
            'ix-ssl',
            {'onetime': True}
        )

        return await self._get_instance(pk)

    @accepts(
        Dict(
            'ca_sign_csr',
            Int('ca_id', required=True),
            Int('csr_cert_id', required=True),
            Str('name', required=True),
        ),
        Str('schema_name', default='certificate_authority_update')
    )
    async def ca_sign_csr(self, data, schema_name):
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
                try:
                    csr = crypto.load_certificate_request(crypto.FILETYPE_PEM, csr_cert_data['CSR'])
                except crypto.Error:
                    verrors.add(
                        f'{schema_name}.csr_cert_id',
                        'CSR not valid'
                    )

        if verrors:
            raise verrors

        cert_info = crypto.load_certificate(crypto.FILETYPE_PEM, ca_data['certificate'])
        PKey = await self.middleware.call('certificate.load_private_key', ca_data['privatekey'])

        cert = crypto.X509()
        cert.set_serial_number(int(random.random() * (1 << 160)))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(86400 * 365 * 10)
        cert.set_issuer(cert_info.get_subject())
        cert.set_subject(csr.get_subject())
        cert.set_pubkey(csr.get_pubkey())
        cert.sign(PKey, ca_data['digest_algorithm'])

        new_cert = crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode()

        new_csr = {
            'type': CERT_TYPE_INTERNAL,
            'name': data['name'],
            'certificate': new_cert,
            'privatekey': csr_cert_data['privatekey'],
            'create_type': 'CERTIFICATE_CREATE'
        }

        new_csr_dict = await self.middleware.call(
            'certificate.create',
            new_csr
        )

        return new_csr_dict

    @accepts(
        Patch(
            'ca_create_interal', 'ca_create_intermediate',
            ('add', {'name': 'signedby', 'type': 'str', 'required': True}),
        ),
    )
    async def __create_intermediate_ca(self, data):
        data['type'] = CA_TYPE_INTERMEDIATE
        cert_info = get_cert_info_from_data(data)

        signing_cert = await self._get_instance(data['signedby'])

        publickey = await self.middleware.call('certificate.generate_key', data['key_length'])
        signkey = await self.middleware.call('certificate.load_private_key', signing_cert['privatekey'])

        cert = await self.middleware.call('certificate.create_certificate', cert_info)
        cert.set_pubkey(publickey)
        cacert = crypto.load_certificate(crypto.FILETYPE_PEM, signing_cert['certificate'])
        cert.set_issuer(cacert.get_subject())
        cert.add_extensions([
            crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE, pathlen:0"),
            crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
            crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
        ])

        cert.set_serial_number(signing_cert['serial'])
        data['serial'] = 0o3
        cert.sign(signkey, data['digest_algorithm'])

        data['certificate'] = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        data['privatekey'] = crypto.dump_privatekey(crypto.FILETYPE_PEM, publickey)

        await self.do_update(
            signing_cert['id'],
            {
                'serial': signing_cert['serial'] + 1,
                'start_ssl': False
            },
        )

        return data

    @accepts(
        Patch(
            'ca_create', 'ca_create_imported',
            ('edit', _set_required('certificate')),
            ('edit', _set_required('serial')),
            ('rm', {'name': 'create_type'}),
        )
    )
    async def __create_imported_ca(self, data):
        data['type'] = CA_TYPE_EXISTING
        data['chain'] = True if len(RE_CERTIFICATE.findall(data['certificate'])) > 1 else False

        for k, v in (await self.middleware.call('certificate.load_certificate', data['certificate'])).items():
            data[k] = v

        if all(k in data for k in ('passphrase', 'privatekey')):
            private_key = await self.middleware.call(
                'certificate.export_private_key',
                data['privatekey'],
                data['passphrase'])
            data['privatekey'] = private_key

        data.pop('passphrase', None)
        data.pop('passphrase2', None)

        return data

    @accepts(
        Patch(
            'ca_create', 'ca_create_interal',
            ('edit', _set_required('key_length')),
            ('edit', _set_required('digest_algorithm')),
            ('edit', _set_required('lifetime')),
            ('edit', _set_required('country')),
            ('edit', _set_required('state')),
            ('edit', _set_required('city')),
            ('edit', _set_required('organization')),
            ('edit', _set_required('email')),
            ('edit', _set_required('common')),
            ('rm', {'name': 'create_type'}),
            register=True
        )
    )
    async def __create_internal(self, data):
        cert_info = get_cert_info_from_data(data)
        (cert, key) = await self.create_self_signed_CA(cert_info)

        data['type'] = CA_TYPE_INTERNAL
        data['certificate'] = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        data['privatekey'] = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
        data['serial'] = 0o2

        return data

    @accepts(
        Int('id', required=True),
        Patch(
            'ca_create', 'ca_update',
            ('attr', {'update': True}),
            ('add', {'type': 'bool', 'name': 'start_ssl'}),
            ('edit', {'name': 'create_type', 'method': lambda attr: attr.enum.append('CA_SIGN_CSR')})
        ),
    )
    async def do_update(self, id, data):
        # TODO: SHOULD ALL FIELDS BE ALLOWED FOR UPDATE?

        if data.pop('create_type', '') == 'CA_SIGN_CSR':
            data['ca_id'] = id
            return await self.ca_sign_csr(data, 'certificate_authority_update')

        old = await self._get_instance(id)
        # signedby is changed back to integer from a dict
        old['signedby'] = old['signedby']['id'] if old.get('signedby') else None

        new = old.copy()
        new.update(data)

        verrors = await self.validate_common_attributes(new, 'certificate_authority_update')

        required_fields = ['certificate', 'name', 'serial']
        for field in required_fields:
            if not new.get(field):
                verrors.add(
                    f'certificate_authority_update.{field}',
                    f'{field} is required'
                )

        if new['name'] != old['name']:
            await validate_cert_name(self.middleware, data['name'], self._config.datastore, verrors,
                                     'certificate_authority_update.name')

        if verrors:
            raise verrors

        new['san'] = ' '.join(new['san']) if data.get('san') else ''

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if data.pop('start_ssl', True):
            await self.middleware.call(
                'service.start',
                'ix-ssl',
                {'onetime': True}
            )

        return await self._get_instance(id)

    @accepts(
            Int('id')
        )
    async def do_delete(self, id):
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call(
            'service.start',
            'ix-ssl',
            {'onetime': True}
        )
        return response
