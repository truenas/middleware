import copy
import datetime
import josepy as jose
import os
import random
import re
import subprocess

from middlewared.async_validators import validate_country
from middlewared.plugins.crypto_.utils import DEFAULT_LIFETIME_DAYS, EC_CURVES, EC_CURVE_DEFAULT, EKU_OIDS, RE_CERTIFICATE
from middlewared.schema import accepts, Bool, Datetime, Dict, Int, List, OROperator, Patch, Ref, returns, Str
from middlewared.service import CallError, CRUDService, job, periodic, private, skip_arg, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.validators import Email, Range
from middlewared.utils import osc

from acme import errors, messages
from OpenSSL import crypto

from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


CA_TYPE_EXISTING = 0x01
CA_TYPE_INTERNAL = 0x02
CA_TYPE_INTERMEDIATE = 0x04
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_INTERNAL = 0x10
CERT_TYPE_CSR = 0x20

CERT_ROOT_PATH = '/etc/certificates'
CERT_CA_ROOT_PATH = '/etc/certificates/CA'


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
        data = await self.get_instance(int(cert_id))
        names = [data['common']] if data['common'] else []
        names.extend(data['san'])
        return names

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
        *[Str(k, enum=[k]) for k in EC_CURVES]
    ))
    async def ec_curve_choices(self):
        """
        Dictionary of supported EC curves.
        """
        return {k: k for k in EC_CURVES}

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
            Str('ec_curve', enum=EC_CURVES, default=EC_CURVE_DEFAULT),
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

        return await self.get_instance(pk)

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
        verrors = ValidationErrors()
        cert_info = get_cert_info_from_data(data)
        cert_info['cert_extensions'] = data['cert_extensions']

        if cert_info['cert_extensions']['AuthorityKeyIdentifier']['enabled']:
            verrors.add('cert_extensions.AuthorityKeyIdentifier.enabled', 'This extension is not valid for CSR')

        verrors.check()

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
        old = await self.get_instance(id)
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

        return await self.get_instance(id)

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
    cert_add_to_trusted_store = sa.Column(sa.Boolean(), default=False, nullable=False)


def get_ca_result_entry():
    entry = copy.deepcopy(CertificateService.ENTRY)
    entry.name = 'certificateauthority_entry'
    entry.attrs['add_to_trusted_store'] = Bool('add_to_trusted_store')
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

        ca_data = await self.get_instance(ca_id)

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
                serials.append((await self.get_instance(ca_id))['serial'])

                return serials

            ca_signed_certs.extend((await child_serials(ca_id)))

            # This is for a case where the user might have a malformed certificate and serial value returns None
            ca_signed_certs = list(filter(None, ca_signed_certs))

            if not ca_signed_certs:
                return int(
                    (await self.get_instance(ca_id))['serial'] or 0
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
            ('add', Bool('add_to_trusted_store', default=False)),
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

        return await self.get_instance(pk)

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

        signing_cert = await self.get_instance(data['signedby'])

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
            Bool('add_to_trusted_store'),
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

        old = await self.get_instance(id)
        # signedby is changed back to integer from a dict
        old['signedby'] = old['signedby']['id'] if old.get('signedby') else None

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if any(new[k] != old[k] for k in ('name', 'revoked', 'add_to_trusted_store')):
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

            if not verrors and new['revoked'] and new['add_to_trusted_store']:
                verrors.add(
                    'certificate_authority_update.add_to_trusted_store',
                    'Revoked certificates cannot be added to system\'s trusted store'
                )

            if verrors:
                raise verrors

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                {'name': new['name'], 'add_to_trusted_store': new['add_to_trusted_store']},
                {'prefix': self._config.datastore_prefix}
            )

            if old['revoked'] != new['revoked'] and new['revoked']:
                await self.revoke_ca_chain(id)

            await self.middleware.call('service.start', 'ssl')

        return await self.get_instance(id)

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
        await self.get_instance(id)
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
