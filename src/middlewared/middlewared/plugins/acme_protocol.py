import copy
import josepy as jose
import json
import requests

from acme import client, messages
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from middlewared.api import api_method
from middlewared.api.base import BaseModel, LongString, single_argument_args
from middlewared.api.current import (
    ACMEDNSAuthenticatorEntry, DNSAuthenticatorCreateArgs, DNSAuthenticatorCreateResult,
    DNSAuthenticatorUpdateArgs, DNSAuthenticatorUpdateResult, DNSAuthenticatorDeleteArgs,
    DNSAuthenticatorDeleteResult,
)
from middlewared.schema import ValidationErrors
from middlewared.service import CallError, CRUDService, private
import middlewared.sqlalchemy as sa


# TODO: See what can be done to respect rate limits


class JWKCreate(BaseModel):
    key_size: int = 2048
    public_exponent: int = 65537


class ACMERegistrationBody(BaseModel):
    id: int
    contact: str
    status: str
    key: LongString


class ACMERegistrationEntry(BaseModel):
    id: int
    uri: str
    directory: str
    tos: str
    new_account_uri: str
    new_nonce_uri: str
    new_order_uri: str
    revoke_cert_uri: str
    body: ACMERegistrationBody


@single_argument_args('acme_registration_create')
class ACMERegistrationCreateArgs(BaseModel):
    tos: bool = False
    JWK_create: JWKCreate = JWKCreate()
    acme_directory_uri: str


class ACMERegistrationCreateResult(BaseModel):
    result: ACMERegistrationEntry


class ACMERegistrationModel(sa.Model):
    __tablename__ = 'system_acmeregistration'

    id = sa.Column(sa.Integer(), primary_key=True)
    uri = sa.Column(sa.String(200))
    directory = sa.Column(sa.String(200), unique=True)
    tos = sa.Column(sa.String(200))
    new_account_uri = sa.Column(sa.String(200))
    new_nonce_uri = sa.Column(sa.String(200))
    new_order_uri = sa.Column(sa.String(200))
    revoke_cert_uri = sa.Column(sa.String(200))


class ACMERegistrationBodyModel(sa.Model):
    __tablename__ = 'system_acmeregistrationbody'

    id = sa.Column(sa.Integer(), primary_key=True)
    status = sa.Column(sa.String(10))
    key = sa.Column(sa.Text())
    acme_id = sa.Column(sa.ForeignKey('system_acmeregistration.id'), index=True)


class ACMERegistrationService(CRUDService):

    class Config:
        datastore = 'system.acmeregistration'
        datastore_extend = 'acme.registration.register_extend'
        namespace = 'acme.registration'
        private = True
        entry = ACMERegistrationEntry

    @private
    async def register_extend(self, data):
        data['body'] = {
            key: value for key, value in
            (await self.middleware.call(
                'datastore.query', 'system.acmeregistrationbody',
                [['acme', '=', data['id']]], {'get': True}
            )).items() if key != 'acme'
        }
        return data

    @private
    def get_directory(self, acme_directory_uri):
        self.middleware.call_sync('network.general.will_perform_activity', 'acme')

        try:
            acme_directory_uri = acme_directory_uri.rstrip('/')
            response = requests.get(acme_directory_uri).json()
            return messages.Directory({
                key: response[key] for key in ['newAccount', 'newNonce', 'newOrder', 'revokeCert']
            })
        except (requests.ConnectionError, requests.Timeout, json.JSONDecodeError, KeyError) as e:
            raise CallError(f'Unable to retrieve directory : {e}')

    @api_method(ACMERegistrationCreateArgs, ACMERegistrationCreateResult, private=True)
    def do_create(self, data):
        """
        Register with ACME Server

        Create a registration for a specific ACME Server registering root user with it

        `acme_directory_uri` is a directory endpoint for any ACME Server

        .. examples(websocket)::

          Register with ACME Server

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "acme.registration.create",
                "params": [{
                    "tos": true,
                    "acme_directory_uri": "https://acme-staging-v02.api.letsencrypt.org/directory"
                    "JWK_create": {
                        "key_size": 2048,
                        "public_exponent": 65537
                    }
                }]
            }
        """
        # STEPS FOR CREATION
        # 1) CREATE KEY
        # 2) REGISTER CLIENT
        # 3) SAVE REGISTRATION OBJECT
        # 4) SAVE REGISTRATION BODY

        verrors = ValidationErrors()
        directory = self.get_directory(data['acme_directory_uri'])
        if not isinstance(directory, messages.Directory):
            verrors.add(
                'acme_registration_create.acme_directory_uri',
                f'System was unable to retrieve the directory with the specified acme_directory_uri: {directory}'
            )

        # Normalizing uri after directory call as let's encrypt staging api
        # does not accept a trailing slash right now
        data['acme_directory_uri'] += '/' if data['acme_directory_uri'][-1] != '/' else ''

        if not data['tos']:
            verrors.add(
                'acme_registration_create.tos',
                'Please agree to the terms of service'
            )

        if self.middleware.call_sync(
            'acme.registration.query', [['directory', '=', data['acme_directory_uri']]]
        ):
            verrors.add(
                'acme_registration_create.acme_directory_uri',
                'A registration with the specified directory uri already exists'
            )

        verrors.check()

        key = jose.JWKRSA(key=rsa.generate_private_key(
            public_exponent=data['JWK_create']['public_exponent'],
            key_size=data['JWK_create']['key_size'],
            backend=default_backend()
        ))
        acme_client = client.ClientV2(directory, client.ClientNetwork(key))
        register = acme_client.new_account(
            messages.NewRegistration.from_data(
                terms_of_service_agreed=True
            )
        )
        # We have registered with the acme server

        # Save registration object
        registration_id = self.middleware.call_sync(
            'datastore.insert',
            self._config.datastore,
            {
                'uri': register.uri,
                'tos': register.terms_of_service or '',
                'new_account_uri': directory.newAccount,
                'new_nonce_uri': directory.newNonce,
                'new_order_uri': directory.newOrder,
                'revoke_cert_uri': directory.revokeCert,
                'directory': data['acme_directory_uri']
            }
        )

        # Save registration body
        self.middleware.call_sync(
            'datastore.insert',
            'system.acmeregistrationbody',
            {
                'status': register.body.status,
                'key': key.json_dumps(),
                'acme': registration_id
            }
        )

        return self.middleware.call_sync(f'{self._config.namespace}.get_instance', registration_id)


class ACMEDNSAuthenticatorModel(sa.Model):
    __tablename__ = 'system_acmednsauthenticator'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(64), unique=True)
    attributes = sa.Column(sa.JSON(encrypted=True))


class DNSAuthenticatorService(CRUDService):

    class Config:
        namespace = 'acme.dns.authenticator'
        datastore = 'system.acmednsauthenticator'
        cli_namespace = 'system.acme.dns_auth'
        entry = ACMEDNSAuthenticatorEntry
        role_prefix = 'NETWORK_INTERFACE'

    @private
    async def common_validation(self, data, schema_name, old=None):
        verrors = ValidationErrors()
        filters = [['name', '!=', old['name']]] if old else []
        filters.append(['name', '=', data['name']])
        if await self.query(filters):
            verrors.add(f'{schema_name}.name', 'Specified name is already in use')

        if old and old['attributes']['authenticator'] != data['attributes']['authenticator']:
            verrors.add(f'{schema_name}.attributes.authenticator', 'Authenticator cannot be changed')

        authenticator_obj = await self.middleware.call(
            'acme.dns.authenticator.get_authenticator_internal', data['attributes']['authenticator']
        )
        data['attributes'] = await authenticator_obj.validate_credentials(self.middleware, data['attributes'])

        verrors.check()

    @api_method(DNSAuthenticatorCreateArgs, DNSAuthenticatorCreateResult)
    async def do_create(self, data):
        """
        Create a DNS Authenticator

        Create a specific DNS Authenticator containing required authentication details for the said
        provider to successfully connect with it

        .. examples(websocket)::

          Create a DNS Authenticator for Route53

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "acme.dns.authenticator.create",
                "params": [{
                    "name": "route53_authenticator",
                    "attributes": {
                        "access_key_id": "AQX13",
                        "secret_access_key": "JKW90",
                        "authenticator": "route53"
                    }
                }]
            }
        """
        await self.common_validation(data, 'dns_authenticator_create')

        id_ = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
        )

        return await self.get_instance(id_)

    @api_method(DNSAuthenticatorUpdateArgs, DNSAuthenticatorUpdateResult)
    async def do_update(self, id_, data):
        """
        Update DNS Authenticator of `id`

        .. examples(websocket)::

          Update a DNS Authenticator of `id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "acme.dns.authenticator.update",
                "params": [
                    1,
                    {
                        "name": "route53_authenticator",
                        "attributes": {
                            "access_key_id": "AQX13",
                            "secret_access_key": "JKW90",
                            "authenticator": "route53"
                        }
                    }
                ]
            }
        """
        old = await self.get_instance(id_)
        new = copy.deepcopy(old)
        attrs = data.pop('attributes', {})
        new['attributes'].update(attrs)
        new.update(data)

        await self.common_validation(new, 'dns_authenticator_update', old)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new
        )

        return await self.get_instance(id_)

    @api_method(DNSAuthenticatorDeleteArgs, DNSAuthenticatorDeleteResult)
    async def do_delete(self, id_):
        """
        Delete DNS Authenticator of `id`

        .. examples(websocket)::

          Delete a DNS Authenticator of `id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "acme.dns.authenticator.delete",
                "params": [
                    1
                ]
            }
        """
        await self.middleware.call('certificate.delete_domains_authenticator', id_)

        return await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id_
        )


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'acme', 'ACME')
