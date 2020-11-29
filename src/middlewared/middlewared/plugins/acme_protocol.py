import boto3
import josepy as jose
import json
import requests
import time

from middlewared.schema import Bool, Dict, Int, Str, ValidationErrors
from middlewared.service import accepts, CallError, CRUDService, private
import middlewared.sqlalchemy as sa
from middlewared.validators import validate_attributes

from acme import client, messages
from botocore import exceptions as boto_exceptions
from botocore.errorfactory import BaseClientExceptions as boto_BaseClientException
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa


# TODO: See what can be done to respect rate limits


class ACMERegistrationModel(sa.Model):
    __tablename__ = 'system_acmeregistration'

    id = sa.Column(sa.Integer(), primary_key=True)
    uri = sa.Column(sa.String(200))
    directory = sa.Column(sa.String(200))
    tos = sa.Column(sa.String(200))
    new_account_uri = sa.Column(sa.String(200))
    new_nonce_uri = sa.Column(sa.String(200))
    new_order_uri = sa.Column(sa.String(200))
    revoke_cert_uri = sa.Column(sa.String(200))


class ACMERegistrationBodyModel(sa.Model):
    __tablename__ = 'system_acmeregistrationbody'

    id = sa.Column(sa.Integer(), primary_key=True)
    contact = sa.Column(sa.String(254))
    status = sa.Column(sa.String(10))
    key = sa.Column(sa.Text())
    acme_id = sa.Column(sa.ForeignKey('system_acmeregistration.id'), index=True)


class ACMERegistrationService(CRUDService):

    class Config:
        datastore = 'system.acmeregistration'
        datastore_extend = 'acme.registration.register_extend'
        namespace = 'acme.registration'
        private = True

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

    @accepts(
        Dict(
            'acme_registration_create',
            Bool('tos', default=False),
            Dict(
                'JWK_create',
                Int('key_size', default=2048),
                Int('public_exponent', default=65537)
            ),
            Str('acme_directory_uri', required=True),
        )
    )
    def do_create(self, data):
        """
        Register with ACME Server

        Create a regisration for a specific ACME Server registering root user with it

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

        self.middleware.call_sync('network.general.will_perform_activity', 'acme')

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

        # For now we assume that only root is responsible for certs issued under ACME protocol
        email = (self.middleware.call_sync('user.query', [['uid', '=', 0]]))[0]['email']
        if not email:
            raise CallError(
                'Please specify root email address which will be used with the ACME server'
            )

        if self.middleware.call_sync(
            'acme.registration.query', [['directory', '=', data['acme_directory_uri']]]
        ):
            verrors.add(
                'acme_registration_create.acme_directory_uri',
                'A registration with the specified directory uri already exists'
            )

        if verrors:
            raise verrors

        key = jose.JWKRSA(key=rsa.generate_private_key(
            public_exponent=data['JWK_create']['public_exponent'],
            key_size=data['JWK_create']['key_size'],
            backend=default_backend()
        ))
        acme_client = client.ClientV2(directory, client.ClientNetwork(key))
        register = acme_client.new_account(
            messages.NewRegistration.from_data(
                email=email,
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
                'tos': register.terms_of_service,
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
                'contact': register.body.contact[0],
                'status': register.body.status,
                'key': key.json_dumps(),
                'acme': registration_id
            }
        )

        return self.middleware.call_sync(f'{self._config.namespace}._get_instance', registration_id)


class ACMEDNSAuthenticatorModel(sa.Model):
    __tablename__ = 'system_acmednsauthenticator'

    id = sa.Column(sa.Integer(), primary_key=True)
    authenticator = sa.Column(sa.String(64))
    name = sa.Column(sa.String(64))
    attributes = sa.Column(sa.JSON(encrypted=True))


class DNSAuthenticatorService(CRUDService):

    class Config:
        namespace = 'acme.dns.authenticator'
        datastore = 'system.acmednsauthenticator'
        cli_namespace = 'system.acme.dns_auth'

    def __init__(self, *args, **kwargs):
        super(DNSAuthenticatorService, self).__init__(*args, **kwargs)
        self.schemas = DNSAuthenticatorService.initialize_authenticator_schemas()

    @accepts()
    def authenticator_schemas(self):
        """
        Get the schemas for all DNS providers we support for ACME DNS Challenge and the respective attributes
        required for connecting to them while validating a DNS Challenge
        """
        return [
            {'schema': [v.to_json_schema() for v in value], 'key': key}
            for key, value in self.schemas.items()
        ]

    @staticmethod
    @private
    def initialize_authenticator_schemas():

        return {
            f_n[len('update_txt_record_'):]: [
                Str(arg, required=True)
                for arg in list(getattr(DNSAuthenticatorService, f_n).__code__.co_varnames)
                [4: getattr(DNSAuthenticatorService, f_n).__code__.co_argcount]
            ]
            for f_n in [
                func for func in dir(DNSAuthenticatorService)
                if callable(getattr(DNSAuthenticatorService, func)) and func.startswith('update_txt_record_')
            ]
        }

    @private
    async def common_validation(self, data, schema_name):
        verrors = ValidationErrors()
        if data['authenticator'] not in self.schemas:
            verrors.add(
                f'{schema_name}.authenticator',
                f'System does not support {data["authenticator"]} as an Authenticator'
            )
        else:
            verrors = validate_attributes(self.schemas[data['authenticator']], data)

        if verrors:
            raise verrors

    @accepts(
        Dict(
            'dns_authenticator_create',
            Str('authenticator', required=True),
            Str('name', required=True),
            Dict('attributes', additional_attrs=True, required=True)
        )
    )
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
                    "authenticator": "route53",
                    "attributes": {
                        "access_key_id": "AQX13",
                        "secret_access_key": "JKW90"
                    }
                }]
            }
        """
        await self.common_validation(data, 'dns_authenticator_create')

        id = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
        )

        return await self._get_instance(id)

    @accepts(
        Int('id'),
        Dict(
            'dns_authenticator_update',
            Str('name'),
            Dict('attributes', additional_attrs=True)
        )
    )
    async def do_update(self, id, data):
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
                            "secret_access_key": "JKW90"
                        }
                    }
                ]
            }
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        await self.common_validation(new, 'dns_authenticator_update')

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new
        )

        return await self._get_instance(id)

    @accepts(
        Int('id', required=True)
    )
    async def do_delete(self, id):
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
        await self.middleware.call('certificate.delete_domains_authenticator', id)

        return await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

    @accepts(
        Dict(
            'update_txt_record',
            Int('authenticator', required=True),
            Str('key', required=True, max_length=None),
            Str('domain', required=True),
            Str('challenge', required=True, max_length=None),
        )
    )
    @private
    def update_txt_record(self, data):
        self.middleware.call_sync('network.general.will_perform_activity', 'acme')

        authenticator = self.middleware.call_sync('acme.dns.authenticator._get_instance', data['authenticator'])

        return self.__getattribute__(
            f'update_txt_record_{authenticator["authenticator"].lower()}'
        )(
            data['domain'],
            messages.ChallengeBody.from_json(json.loads(data['challenge'])),
            jose.JWKRSA.fields_from_json(json.loads(data['key'])),
            **authenticator['attributes']
        )

    '''
    Few rules for writing authenticator functions
    1) The name must start with "update_txt_record_"
    2) The authenticator name in function should be lowercase e.g "route53"
    3) The first 3 arguments must be domain, challenge and key. Rest will be what the
       credentials are required for authenticating and nothing else
    4) In case update_txt_record is unsuccessful, CallError should be RAISED with appropriate
       status/reason.
    '''

    @private
    def update_txt_record_route53(self, domain, challenge, key, access_key_id, secret_access_key):
        session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key
        )
        client = session.client('route53')

        # Finding zone id for the given domain
        paginator = client.get_paginator('list_hosted_zones')
        target_labels = domain.rstrip('.').split('.')
        zones = []
        try:
            for page in paginator.paginate():
                for zone in page['HostedZones']:
                    if zone['Config']['PrivateZone']:
                        continue

                    candidate_labels = zone['Name'].rstrip('.').split('.')
                    if candidate_labels == target_labels[-len(candidate_labels):]:
                        zones.append((zone['Name'], zone['Id']))
            if not zones:
                raise CallError(
                    f'Unable to find a Route53 hosted zone for {domain}'
                )
        except boto_exceptions.ClientError as e:
            raise CallError(
                f'Failed to get Hosted zones with provided credentials :{e}'
            )

        # Order the zones that are suffixes for our desired to domain by
        # length, this puts them in an order like:
        # ["foo.bar.baz.com", "bar.baz.com", "baz.com", "com"]
        # And then we choose the first one, which will be the most specific.
        zones.sort(key=lambda z: len(z[0]), reverse=True)
        zone_id = zones[0][1]

        try:
            resp = client.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': challenge.validation_domain_name(domain),
                                'ResourceRecords': [{'Value': f'"{challenge.validation(key)}"'}],
                                'TTL': 3600,
                                'Type': 'TXT'
                            }
                        }
                    ],
                    'Comment': f'{"Free" if self.middleware.call_sync("system.is_freenas") else "True"}'
                               'NAS-dns-route53 certificate validation'
                }
            )
        except boto_BaseClientException as e:
            raise CallError(
                f'Failed to update record sets : {e}'
            )

        """
        Wait for a change to be propagated to all Route53 DNS servers.
        https://docs.aws.amazon.com/Route53/latest/APIReference/API_GetChange.html
        """
        for unused_n in range(0, 120):
            r = client.get_change(Id=resp['ChangeInfo']['Id'])
            if r['ChangeInfo']['Status'] == 'INSYNC':
                return resp['ChangeInfo']['Id']
            time.sleep(5)

        raise CallError(
            f'Timed out waiting for Route53 change. Current status: {resp["ChangeInfo"]["Status"]}'
        )


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'acme', 'ACME')
