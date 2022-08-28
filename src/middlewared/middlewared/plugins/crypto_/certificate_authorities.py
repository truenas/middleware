import random

from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors
import middlewared.sqlalchemy as sa

from .cert_entry import get_ca_result_entry
from .common_validation import _validate_common_attributes, validate_cert_name
from .dependencies import check_dependencies
from .key_utils import export_private_key
from .load_utils import get_serial_from_certificate_safe
from .query_utils import get_ca_chain, normalize_cert_attrs
from .utils import (
    get_cert_info_from_data, _set_required, CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE
)


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


class CertificateAuthorityService(CRUDService):

    class Config:
        datastore = 'system.certificateauthority'
        datastore_extend = 'certificateauthority.cert_extend'
        datastore_extend_context = 'certificateauthority.cert_extend_context'
        datastore_prefix = 'cert_'
        cli_namespace = 'system.certificate.authority'

    ENTRY = get_ca_result_entry()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.map_create_functions = {
            'CA_CREATE_INTERNAL': 'create_internal',
            'CA_CREATE_IMPORTED': 'create_imported_ca',
            'CA_CREATE_INTERMEDIATE': 'create_intermediate_ca',
        }

    @private
    def cert_extend_context(self, rows, extra):
        context = {
            'cas': {c['id']: c for c in self.middleware.call_sync(
                'datastore.query', 'system.certificateauthority', [], {'prefix': 'cert_'}
            )},
            'certs': {
                c['id']: c for c in self.middleware.call_sync(
                    'datastore.query', 'system.certificate', [], {'prefix': 'cert_'}
                )
            },
        }

        signed_mapping = {}
        for ca in context['cas'].values():
            signed_mapping[ca['id']] = 0
            for cert in context['certs'].values():
                if cert['signedby'] and cert['signedby']['id'] == ca['id']:
                    signed_mapping[ca['id']] += 1

        context['signed_mapping'] = signed_mapping
        return context

    @private
    def cert_extend(self, cert, context):
        if cert['signedby']:
            cert['signedby'] = self.cert_extend(context['cas'][cert['signedby']['id']], context)

        normalize_cert_attrs(cert)
        cert['signed_certificates'] = context['signed_mapping'][cert['id']]
        cert.update({
            'revoked_certs': list(filter(
                lambda c: c['revoked_date'],
                get_ca_chain(cert['id'], context['certs'].values(), context['cas'].values())
            )),
        })
        return cert

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
    def get_serial_for_certificate(self, ca_id):

        ca_data = self.middleware.call_sync(
            'datastore.query', 'system.certificateauthority', [['id', '=', ca_id]], {'get': True, 'prefix': 'cert_'}
        )

        if ca_data.get('signedby'):
            # Recursively call the same function for it's parent and let the function gather all serials in a chain
            return self.get_serial_for_certificate(ca_data['signedby']['id'])
        else:

            def cert_serials(ca_id):
                serials = []
                for cert in filter(
                    lambda c: c['certificate'],
                    self.middleware.call_sync(
                        'datastore.query', 'system.certificate', [['signedby', '=', ca_id]], {'prefix': 'cert_'}
                    )
                ):
                    serial = get_serial_from_certificate_safe(cert['certificate'])
                    if serial is not None:
                        serials.append(serial)
                return serials

            ca_signed_certs = cert_serials(ca_id)

            def child_serials(ca):
                serials = []
                for child in filter(
                    lambda c: c['certificate'],
                    self.middleware.call_sync(
                        'datastore.query', 'system.certificateauthority',
                        [['signedby', '=', ca['id']]], {'prefix': 'cert_'}
                    )
                ):
                    serials.extend(child_serials(child))

                serials.extend(cert_serials(ca['id']))
                serial = get_serial_from_certificate_safe(ca['certificate'])
                if serial is not None:
                    serials.append(serial)

                return serials

            ca_signed_certs.extend(child_serials(ca_data))

            # This is for a case where the user might have a malformed certificate and serial value returns None
            ca_signed_certs = list(filter(None, ca_signed_certs))

            if not ca_signed_certs:
                return int(get_serial_from_certificate_safe(ca_data['certificate']) or 0) + 1
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
    # CA_CREATE_INTERNAL          - create_internal
    # CA_CREATE_IMPORTED          - create_imported_ca
    # CA_CREATE_INTERMEDIATE      - create_intermediate_ca

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

        verrors.check()

        data = {
            k: v for k, v in (
                await self.middleware.call(f'certificateauthority.{self.map_create_functions[create_type]}', data)
            ).items()
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
        Patch(
            'ca_create_internal', 'ca_create_intermediate',
            ('add', {'name': 'signedby', 'type': 'int', 'required': True}),
        ),
    )
    @private
    async def create_intermediate_ca(self, data):

        signing_cert = await self.get_instance(data['signedby'])

        serial = await self.middleware.call('certificateauthority.get_serial_for_certificate', signing_cert['id'])

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
    @private
    def create_imported_ca(self, data):
        data['type'] = CA_TYPE_EXISTING

        if all(k in data for k in ('passphrase', 'privatekey')):
            data['privatekey'] = export_private_key(data['privatekey'], data['passphrase'])

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
    @private
    async def create_internal(self, data):
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
            return await self.middleware.call(
                'certificateauthority.ca_sign_csr_impl', data, 'certificate_authority_update'
            )
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
                await self.middleware.call('certificateauthority.revoke_ca_chain', id)

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
