import datetime

from truenas_crypto_utils.csr import generate_certificate_signing_request
from truenas_crypto_utils.read import load_certificate, load_certificate_request, RE_CERTIFICATE
from truenas_crypto_utils.validation import validate_certificate_with_key, validate_private_key

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    CertificateEntry, CertificateCreateArgs, CertificateCreateResult, CertificateUpdateArgs,
    CertificateUpdateResult, CertificateDeleteArgs, CertificateDeleteResult,
)
from middlewared.async_validators import validate_country
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors

from .query_utils import normalize_cert_attrs
from .private_models import (
    CertificateCreateACMEArgs, CertificateCreateCSRArgs, CertificateCreateImportedCSRArgs,
    CertificateCreateImportedCertificateArgs, CertificateCreateInternalResult,
)
from .utils import CERT_TYPE_EXISTING, CERT_TYPE_CSR, get_cert_info_from_data, get_private_key


class CertificateModel(sa.Model):
    __tablename__ = 'system_certificate'

    id = sa.Column(sa.Integer(), primary_key=True)
    cert_type = sa.Column(sa.Integer())
    cert_name = sa.Column(sa.String(120), unique=True)
    cert_certificate = sa.Column(sa.Text(), nullable=True)
    cert_privatekey = sa.Column(sa.EncryptedText(), nullable=True)
    cert_CSR = sa.Column(sa.Text(), nullable=True)
    cert_acme_uri = sa.Column(sa.String(200), nullable=True)
    cert_domains_authenticators = sa.Column(sa.JSON(encrypted=True), nullable=True)
    cert_renew_days = sa.Column(sa.Integer(), nullable=True, default=10)
    cert_acme_id = sa.Column(sa.ForeignKey('system_acmeregistration.id'), index=True, nullable=True)
    cert_add_to_trusted_store = sa.Column(sa.Boolean(), default=False, nullable=False)


class CertificateService(CRUDService):

    class Config:
        datastore = 'system.certificate'
        datastore_extend = 'certificate.cert_extend'
        datastore_prefix = 'cert_'
        cli_namespace = 'system.certificate'
        role_prefix = 'CERTIFICATE'
        entry = CertificateEntry

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_functions = {
            'CERTIFICATE_CREATE_IMPORTED': 'create_imported_certificate',
            'CERTIFICATE_CREATE_IMPORTED_CSR': 'create_imported_csr',
            'CERTIFICATE_CREATE_CSR': 'create_csr',
            'CERTIFICATE_CREATE_ACME': 'create_acme_certificate',
        }

    @private
    def cert_extend(self, cert):
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

    @private
    async def validate_cert_name(self, cert_name, schema_name, verrors):
        if await self.middleware.call('datastore.query', self._config.datastore, [('cert_name', '=', cert_name)]):
            verrors.add(
                f'{schema_name}.name',
                'A certificate with this name already exists'
            )

    @private
    async def validate_common_attributes(self, data, schema_name):
        verrors = ValidationErrors()
        create_type = data['create_type']

        await self.validate_cert_name(data['name'], schema_name, verrors)

        if country := data.get('country'):
            await validate_country(self.middleware, country, verrors, f'{schema_name}.country')

        if certificate := data.get('certificate'):
            matches = RE_CERTIFICATE.findall(certificate)

            if not matches or not await self.middleware.run_in_thread(load_certificate, certificate):
                verrors.add(
                    f'{schema_name}.certificate',
                    'Not a valid certificate'
                )

        private_key = data.get('privatekey')
        passphrase = data.get('passphrase')
        if private_key:
            if err := await self.middleware.run_in_thread(validate_private_key, private_key, passphrase):
                verrors.add(f'{schema_name}.privatekey', err)

        if csr := data.get('CSR'):
            if not await self.middleware.run_in_thread(load_certificate_request, csr):
                verrors.add(
                    f'{schema_name}.CSR',
                    'Please provide a valid CSR'
                )

        csr_id = data.get('csr_id')
        if csr_id and not await self.middleware.call(
            'certificate.query', [['id', '=', csr_id], ['cert_type_CSR', '=', True]]
        ):
            verrors.add(
                f'{schema_name}.csr_id',
                'Please provide a valid csr_id'
            )

        if not verrors and create_type == 'CERTIFICATE_CREATE_IMPORTED' and (err := await self.middleware.run_in_thread(
            validate_certificate_with_key, certificate, private_key, passphrase
        )):
            verrors.add(
                f'{schema_name}.privatekey',
                f'Private key does not match certificate: {err}'
            )

        if create_type == 'CERTIFICATE_CREATE_CSR':
            key_type = data.get('key_type')
            if not key_type:
                verrors.add(
                    f'{schema_name}.key_type',
                    'This field is required.'
                )
            elif key_type != 'EC':
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

            if cert_extensions := data.get('cert_extensions'):
                verrors.extend(
                    (await self.middleware.call('cryptokey.validate_extensions', cert_extensions, schema_name))
                )

        return verrors

    # CREATE METHODS FOR CREATING CERTIFICATES
    # "do_create" IS CALLED FIRST AND THEN BASED ON THE TYPE OF THE CERTIFICATE WHICH IS TO BE CREATED THE
    # APPROPRIATE METHOD IS CALLED
    # FOLLOWING TYPES ARE SUPPORTED
    # CREATE_TYPE ( STRING )          - METHOD CALLED
    # CERTIFICATE_CREATE_IMPORTED     - create_imported_certificate
    # CERTIFICATE_CREATE_IMPORTED_CSR - create_imported_csr
    # CERTIFICATE_CREATE_CSR          - create_csr
    # CERTIFICATE_CREATE_ACME         - create_acme_certificate

    @api_method(CertificateCreateArgs, CertificateCreateResult)
    @job(lock='cert_create')
    async def do_create(self, job, data):
        """
        Create a new Certificate

        Certificates are classified under following types and the necessary keywords to be passed
        for `create_type` attribute to create the respective type of certificate

        1) Imported Certificate                 -  CERTIFICATE_CREATE_IMPORTED

        2) Certificate Signing Request          -  CERTIFICATE_CREATE_CSR

        3) Imported Certificate Signing Request -  CERTIFICATE_CREATE_IMPORTED_CSR

        4) ACME Certificate                     -  CERTIFICATE_CREATE_ACME

        By default, created CSRs use RSA keys. If an Elliptic Curve Key is desired, it can be specified with the
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
        """
        verrors = await self.validate_common_attributes(data, 'certificate_create')
        add_to_trusted_store = data.pop('add_to_trusted_store', False)
        create_type = data.pop('create_type')
        if add_to_trusted_store and create_type in ('CERTIFICATE_CREATE_IMPORTED_CSR', 'CERTIFICATE_CREATE_CSR'):
            verrors.add('certificate_create.add_to_trusted_store', 'Cannot add CSR to trusted store')

        verrors.check()

        job.set_progress(10, 'Initial validation complete')

        payload_keys = []
        if create_type == 'CERTIFICATE_CREATE_IMPORTED':
            payload_keys = ['name', 'certificate', 'privatekey', 'passphrase']
        elif create_type == 'CERTIFICATE_CREATE_CSR':
            payload_keys = [
                'name', 'key_length', 'key_type', 'ec_curve', 'passphrase', 'city', 'common', 'country', 'email',
                'organization', 'organizational_unit', 'state', 'digest_algorithm', 'san', 'cert_extensions',
            ]
        elif create_type == 'CERTIFICATE_CREATE_IMPORTED_CSR':
            payload_keys = ['name', 'CSR', 'privatekey', 'passphrase']
        elif create_type == 'CERTIFICATE_CREATE_ACME':
            payload_keys = ['name', 'tos', 'csr_id', 'renew_days', 'acme_directory_uri', 'dns_mapping']

        db_payload = await self.middleware.call(f'certificate.{self.map_functions[create_type]}', job, {
            k: data[k] for k in payload_keys
        }) | {
            'name': data['name'],
            'add_to_trusted_store': add_to_trusted_store,
        }

        pk = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            db_payload,
            {'prefix': self._config.datastore_prefix}
        )

        await (await self.middleware.call('service.control', 'START', 'ssl')).wait(raise_error=True)

        job.set_progress(100, 'Certificate created successfully')

        return await self.get_instance(pk)

    @api_method(CertificateCreateACMEArgs, CertificateCreateInternalResult, private=True, skip_args=1)
    def create_acme_certificate(self, job, data):
        csr_data = self.middleware.call_sync('certificate.get_instance', data['csr_id'])

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
            'renew_days': data['renew_days'],
        }

        return cert_dict

    @api_method(CertificateCreateCSRArgs, CertificateCreateInternalResult, private=True, skip_args=1)
    def create_csr(self, job, data):
        cert_info = get_cert_info_from_data(data)
        cert_info['cert_extensions'] = data['cert_extensions']
        req, key = generate_certificate_signing_request(cert_info)
        job.set_progress(90, 'Finalizing changes')

        return {
            'CSR': req,
            'privatekey': key,
            'type': CERT_TYPE_CSR,
        }

    @api_method(CertificateCreateImportedCSRArgs, CertificateCreateInternalResult, private=True, skip_args=1)
    def create_imported_csr(self, job, data):
        # FIXME: Validate private key matches CSR
        job.set_progress(90, 'Finalizing changes')
        return {
            'CSR': data['CSR'],
            'privatekey': get_private_key(data),
            'type': CERT_TYPE_CSR,
        }

    @api_method(CertificateCreateImportedCertificateArgs, CertificateCreateInternalResult, private=True, skip_args=1)
    def create_imported_certificate(self, job, data):
        job.set_progress(90, 'Finalizing changes')
        return {
            'certificate': data['certificate'],
            'privatekey': get_private_key(data),
            'type': CERT_TYPE_EXISTING,
        }

    @api_method(CertificateUpdateArgs, CertificateUpdateResult)
    @job(lock='cert_update')
    async def do_update(self, job, id_, data):
        """
        Update certificate of `id`

        Only name attribute can be updated.

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
        if old.get('acme'):
            old['acme'] = old['acme']['id']

        new = old.copy()

        new.update(data)

        if any(new.get(k) != old.get(k) for k in ('name', 'renew_days', 'add_to_trusted_store')):

            verrors = ValidationErrors()
            tnc_config = await self.middleware.call('tn_connect.config')
            if tnc_config['certificate'] == id_:
                verrors.add(
                    'certificate_update.name',
                    'This certificate is being used by TrueNAS Connect service and cannot be modified'
                )
                verrors.check()

            if new['name'] != old['name']:
                await self.validate_cert_name(new['name'], 'certificate_update', verrors)

            if not new.get('acme') and data.get('renew_days'):
                verrors.add(
                    'certificate_update.renew_days',
                    'Certificate renewal days is only supported for ACME certificates'
                )

            if new['add_to_trusted_store'] and new['cert_type_CSR']:
                verrors.add(
                    'certificate_update.add_to_trusted_store',
                    'A CSR cannot be added to the system\'s trusted store'
                )

            verrors.check()

            to_update = {'renew_days': new['renew_days']} if data.get('renew_days') else {}

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id_,
                {'name': new['name'], 'add_to_trusted_store': new['add_to_trusted_store'], **to_update},
                {'prefix': self._config.datastore_prefix}
            )

            await (await self.middleware.call('service.control', 'START', 'ssl')).wait(raise_error=True)

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

    @api_method(CertificateDeleteArgs, CertificateDeleteResult)
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

        self.middleware.call_sync('service.control', 'START', 'ssl').wait_sync(raise_error=True)

        self.middleware.call_sync('alert.alert_source_clear_run', 'CertificateChecks')

        job.set_progress(100)
        return response
