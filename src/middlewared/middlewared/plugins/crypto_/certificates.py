import datetime

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Ref, Str
from middlewared.service import CallError, CRUDService, job, private, skip_arg, ValidationErrors
from middlewared.utils.time_utils import utc_now
from middlewared.validators import Email, Range

from .common_validation import _validate_common_attributes, validate_cert_name
from .cert_entry import CERT_ENTRY
from .csr import generate_certificate_signing_request
from .key_utils import export_private_key
from .load_utils import load_certificate
from .query_utils import normalize_cert_attrs
from .utils import (
    CERT_TYPE_EXISTING, CERT_TYPE_INTERNAL, CERT_TYPE_CSR, EC_CURVES, EC_CURVE_DEFAULT,
    get_cert_info_from_data, _set_required,
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
    cert_add_to_trusted_store = sa.Column(sa.Boolean(), default=False, nullable=False)


class CertificateService(CRUDService):

    class Config:
        datastore = 'system.certificate'
        datastore_extend = 'certificate.cert_extend'
        datastore_extend_context = 'certificate.cert_extend_context'
        datastore_prefix = 'cert_'
        cli_namespace = 'system.certificate'
        role_prefix = 'CERTIFICATE'

    ENTRY = CERT_ENTRY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_functions = {
            'CERTIFICATE_CREATE_INTERNAL': 'create_internal',
            'CERTIFICATE_CREATE_IMPORTED': 'create_imported_certificate',
            'CERTIFICATE_CREATE_IMPORTED_CSR': 'create_imported_csr',
            'CERTIFICATE_CREATE_CSR': 'create_csr',
            'CERTIFICATE_CREATE_ACME': 'create_acme_certificate',
        }

    @private
    def cert_extend_context(self, rows, extra):
        context = {
            'cas': {c['id']: c for c in self.middleware.call_sync('certificateauthority.query')},
        }
        return context

    @private
    def cert_extend(self, cert, context):
        if cert['signedby']:
            cert['signedby'] = context['cas'][cert['signedby']['id']]

        normalize_cert_attrs(cert)
        return cert

    @private
    async def cert_services_validation(self, id_, schema_name, raise_verrors=True):
        # General method to check certificate health wrt usage in services
        cert = await self.middleware.call('certificate.query', [['id', '=', id_]])
        verrors = ValidationErrors()
        if cert:
            cert = cert[0]
            if cert['cert_type'] != 'CERTIFICATE' or cert['cert_type_CSR']:
                verrors.add(
                    schema_name,
                    'Selected certificate id is not a valid certificate'
                )
            else:
                await self.cert_checks(cert, verrors, schema_name)
        else:
            verrors.add(
                schema_name,
                f'No Certificate found with the provided id: {id_}'
            )

        if raise_verrors:
            verrors.check()
        else:
            return verrors

    @private
    async def cert_checks(self, cert, verrors, schema_name):
        valid_key_size = {'EC': 28, 'RSA': 2048}
        if not cert.get('fingerprint'):
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
        elif cert['key_length'] < valid_key_size[cert['key_type']]:
            verrors.add(
                schema_name,
                f'{cert["name"]}\'s private key size is less then {valid_key_size[cert["key_type"]]} bits'
            )

        if cert['until'] and datetime.datetime.strptime(
            cert['until'], '%a %b  %d %H:%M:%S %Y'
        ) < datetime.datetime.now():
            verrors.add(
                schema_name,
                f'{cert["name"]!r} has expired (it was valid until {cert["until"]!r})'
            )

        if cert['digest_algorithm'] in ['MD5', 'SHA1']:
            verrors.add(
                schema_name,
                'Please use a certificate whose digest algorithm has at least 112 security bits'
            )

        if cert['revoked']:
            verrors.add(
                schema_name,
                'This certificate is revoked'
            )

    @private
    async def validate_common_attributes(self, data, schema_name):
        verrors = ValidationErrors()

        await _validate_common_attributes(self.middleware, data, verrors, schema_name)

        return verrors

    # CREATE METHODS FOR CREATING CERTIFICATES
    # "do_create" IS CALLED FIRST AND THEN BASED ON THE TYPE OF THE CERTIFICATE WHICH IS TO BE CREATED THE
    # APPROPRIATE METHOD IS CALLED
    # FOLLOWING TYPES ARE SUPPORTED
    # CREATE_TYPE ( STRING )          - METHOD CALLED
    # CERTIFICATE_CREATE_INTERNAL     - create_internal
    # CERTIFICATE_CREATE_IMPORTED     - create_imported_certificate
    # CERTIFICATE_CREATE_IMPORTED_CSR - create_imported_csr
    # CERTIFICATE_CREATE_CSR          - create_csr
    # CERTIFICATE_CREATE_ACME         - create_acme_certificate

    @accepts(
        Dict(
            'certificate_create',
            Bool('tos'),
            Dict('dns_mapping', additional_attrs=True),
            Int('csr_id'),
            Int('signedby'),
            Int('key_length', enum=[2048, 4096]),
            Int('renew_days', validators=[Range(min_=1, max_=30)]),
            Int('type'),
            Int('lifetime'),
            Int('serial', validators=[Range(min_=1)]),
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
            Str('digest_algorithm', enum=['SHA224', 'SHA256', 'SHA384', 'SHA512']),
            List('san', items=[Str('san')]),
            Ref('cert_extensions'),
            Bool('add_to_trusted_store', default=False),
            register=True
        ),
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
        using "SECP384R1" curve.

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

        add_to_trusted_store = data.pop('add_to_trusted_store', False)
        verrors = await self.validate_common_attributes(data, 'certificate_create')
        if add_to_trusted_store and create_type in ('CERTIFICATE_CREATE_IMPORTED_CSR', 'CERTIFICATE_CREATE_CSR'):
            verrors.add('certificate_create.add_to_trusted_store', 'Cannot add CSR to trusted store')

        if create_type == 'CERTIFICATE_CREATE_IMPORTED' and not load_certificate(data['certificate']):
            verrors.add('certificate_create.certificate', 'Unable to parse certificate')

        await validate_cert_name(
            self.middleware, data['name'], self._config.datastore,
            verrors, 'certificate_create.name'
        )

        verrors.check()

        job.set_progress(10, 'Initial validation complete')

        if create_type in (
            'CERTIFICATE_CREATE_IMPORTED_CSR',
            'CERTIFICATE_CREATE_ACME',
            'CERTIFICATE_CREATE_IMPORTED',
        ):
            # We add dictionaries/lists by default, so we need to explicitly remove them
            data.pop('cert_extensions')
            data.pop('san')

        data = {
            k: v for k, v in (
                await self.middleware.call(f'certificate.{self.map_functions[create_type]}', job, data)
            ).items()
            if k in [
                'name', 'certificate', 'CSR', 'privatekey', 'type', 'signedby', 'acme', 'acme_uri',
                'domains_authenticators', 'renew_days', 'add_to_trusted_store',
            ]
        }
        data['add_to_trusted_store'] = add_to_trusted_store

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
            Int('renew_days', default=10, validators=[Range(min_=1)]),
            Str('acme_directory_uri', required=True),
            Str('name', required=True),
            Dict('dns_mapping', additional_attrs=True, required=True)
        )
    )
    @private
    @skip_arg(count=1)
    def create_acme_certificate(self, job, data):

        csr_data = self.middleware.call_sync(
            'certificate.get_instance', data['csr_id']
        )

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
    def create_csr(self, job, data):
        # no signedby, lifetime attributes required
        verrors = ValidationErrors()
        cert_info = get_cert_info_from_data(data)
        cert_info['cert_extensions'] = data['cert_extensions']

        if cert_info['cert_extensions']['AuthorityKeyIdentifier']['enabled']:
            verrors.add('cert_extensions.AuthorityKeyIdentifier.enabled', 'This extension is not valid for CSR')

        verrors.check()

        data['type'] = CERT_TYPE_CSR
        req, key = generate_certificate_signing_request(cert_info)

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
    @private
    @skip_arg(count=1)
    def create_imported_csr(self, job, data):

        # TODO: We should validate csr with private key ?

        data['type'] = CERT_TYPE_CSR

        job.set_progress(80)

        if 'passphrase' in data:
            data['privatekey'] = export_private_key(data['privatekey'], data['passphrase'])

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
    @private
    @skip_arg(count=1)
    def create_imported_certificate(self, job, data):
        verrors = ValidationErrors()

        csr_id = data.pop('csr_id', None)
        if csr_id:
            csr_obj = self.middleware.call_sync(
                'certificate.query', [
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

        verrors.check()

        job.set_progress(50, 'Validation complete')

        data['type'] = CERT_TYPE_EXISTING

        if 'passphrase' in data:
            data['privatekey'] = export_private_key(data['privatekey'], data['passphrase'])

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
            Int('renew_days', validators=[Range(min_=1, max_=30)]),
            Bool('add_to_trusted_store'),
            Str('name'),
        ),
    )
    @job(lock='cert_update')
    async def do_update(self, job, id_, data):
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
        old = await self.get_instance(id_)
        # signedby is changed back to integer from a dict
        old['signedby'] = old['signedby']['id'] if old.get('signedby') else None
        if old.get('acme'):
            old['acme'] = old['acme']['id']

        new = old.copy()

        new.update(data)

        if any(new.get(k) != old.get(k) for k in ('name', 'revoked', 'renew_days', 'add_to_trusted_store')):

            verrors = ValidationErrors()
            tnc_config = await self.middleware.call('tn_connect.config')
            if tnc_config['certificate'] == id_:
                verrors.add(
                    'certificate_update.name',
                    'This certificate is being used by TrueNAS Connect service and cannot be modified'
                )
                verrors.check()

            if new['name'] != old['name']:
                await validate_cert_name(
                    self.middleware, new['name'], self._config.datastore,
                    verrors, 'certificate_update.name'
                )

            if not new.get('acme') and data.get('renew_days'):
                verrors.add(
                    'certificate_update.renew_days',
                    'Certificate renewal days is only supported for ACME certificates'
                )

            if new['revoked'] and new['cert_type_CSR']:
                verrors.add(
                    'certificate_update.revoked',
                    'A CSR cannot be marked as revoked.'
                )
            if new['add_to_trusted_store'] and new['cert_type_CSR']:
                verrors.add(
                    'certificate_update.add_to_trusted_store',
                    'A CSR cannot be added to the system\'s trusted store'
                )
            if new['revoked'] and not old['revoked'] and not new['can_be_revoked']:
                verrors.add(
                    'certificate_update.revoked',
                    'Only certificate(s) can be revoked which have a CA present on the system'
                )
            elif old['revoked'] and not new['revoked']:
                verrors.add(
                    'certificate_update.revoked',
                    'Certificate has already been revoked and this cannot be reversed'
                )

            if not verrors and new['revoked'] and new['add_to_trusted_store']:
                verrors.add(
                    'certificate_update.add_to_trusted_store',
                    'Revoked certificates cannot be added to system\'s trusted store'
                )

            verrors.check()

            to_update = {'renew_days': new['renew_days']} if data.get('renew_days') else {}
            if old['revoked'] != new['revoked'] and new['revoked']:
                to_update['revoked_date'] = utc_now()

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id_,
                {'name': new['name'], 'add_to_trusted_store': new['add_to_trusted_store'], **to_update},
                {'prefix': self._config.datastore_prefix}
            )

            await self.middleware.call('service.start', 'ssl')

        job.set_progress(90, 'Finalizing changes')

        return await self.get_instance(id_)

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
        Bool('force', default=False),
    )
    @job(lock='cert_delete')
    def do_delete(self, job, id_, force):
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
        certificate = self.middleware.call_sync('certificate.get_instance', id_)
        self.middleware.call_sync('certificate.check_cert_deps', id_)

        if certificate.get('acme') and not certificate['expired']:
            # We won't try revoking a certificate which has expired already
            try:
                self.middleware.call_sync(
                    'acme.revoke_certificate', self.middleware.call_sync(
                        'acme.get_acme_client_and_key_payload', certificate['acme']['directory'], True
                    ), certificate['certificate'],
                )
            except CallError:
                if not force:
                    raise

        response = self.middleware.call_sync(
            'datastore.delete',
            self._config.datastore,
            id_
        )

        self.middleware.call_sync('service.start', 'ssl')

        self.middleware.call_sync('alert.alert_source_clear_run', 'CertificateChecks')

        job.set_progress(100)
        return response
