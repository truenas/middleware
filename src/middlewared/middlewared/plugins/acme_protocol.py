import boto3
import josepy as jose
import json
import requests
import time

from middlewared.schema import Bool, Dict, Int, Str, ValidationErrors
from middlewared.service import accepts, CallError, CRUDService
from middlewared.validators import validate_attributes

from acme import client, messages
from botocore import exceptions as boto_exceptions
from botocore.errorfactory import BaseClientExceptions as boto_BaseClientException
from certbot import achallenges
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa


'''
>>> issue_cert
{'name': 'check_cert', 'tos': True, 'csr_id': 14, 'acme_directory_uri': 'https://acme-staging-v02.api.letsencrypt.org/directory', 'create_type': 'CERTIFICATE_CREATE_ACME', 'dns_mapping': {'acmedev.agencialivre.com.br': 1}}
'''

'''
TODO'S:
1) IS THERE A MIN KEY SIZE REQUIRED BY LETS ENCRYPT IN CSR - HANDLE THE EXCEPTION GRACEFULLY
2) CHECK IF _GET_INSTANCE CAN BE CALLED FROM MIDDLEWARE.CALL_SYNC
3) Domain names should not end in periods ? research
4) Integrate alerts
5) See what can be done to respect rate limits
'''


class ACMERegistrationService(CRUDService):

    class Config:
        datastore = 'system.acmeregistration'
        datastore_extend = 'acme.registration.register_extend'
        namespace = 'acme.registration'
        private = True

    async def register_extend(self, data):
        data['body'] = {
            key: value for key, value in
            (await self.middleware.call(
                'datastore.query', 'system.acmeregistrationbody',
                [['acme', '=', data['id']]], {'get': True}
            )).items() if key != 'acme'
        }
        return data

    def get_directory(self, acme_directory_uri):
        try:
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

        # STEPS FOR CREATION
        # 1) CREATE KEY
        # 2) REGISTER CLIENT
        # 3) SAVE REGISTRATION OBJECT
        # 4) SAVE REGISTRATION BODY

        verrors = ValidationErrors()

        directory = self.get_directory(data['acme_directory_uri'])
        if not isinstance(directory, messages.Directory):
            verrors.add(
                'acme_registration_create.directory_uri',
                f'System was unable to retrieve the directory with the specified acme_directory_uri: {directory}'
            )

        if not data['tos']:
            verrors.add(
                'acme_registration_create.tos',
                'Please agree to the terms of service'
            )

        # For now we assume that only root is responsible for certs issued under ACME protocol
        email = (self.middleware.call_sync('user.query', [['id', '=', 1]]))[0]['email']
        if not email:
            raise CallError(
                'Please specify root email address which will be used with the ACME server'
            )

        if self.middleware.call_sync('acme.registration.query', [['directory', '=', data['acme_directory_uri']]]):
            verrors.add(
                'acme_registration_create.directory_uri',
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
                'directory': data['acme_directory_uri'] + '/' if data['acme_directory_uri'][-1] != '/' else ''
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
            },
        )

        return self.middleware.call_sync(f'{self._config.namespace}.query', [('id', '=', registration_id)])[0]


class DNSAuthenticatorService(CRUDService):

    class Config:
        namespace = 'dns.authenticator'
        datastore = 'system.dnsauthenticator'

    def __init__(self, *args, **kwargs):
        super(DNSAuthenticatorService, self).__init__(*args, **kwargs)
        self.schemas = DNSAuthenticatorService.get_authenticator_schemas()

    @staticmethod
    def get_authenticator_schemas():

        return {
            f_n[len('update_txt_record_'):]: [
                Str(arg, required=True)
                for arg in list(getattr(DNSAuthenticatorService, f_n).__code__.co_varnames)
                [4: getattr(DNSAuthenticatorService, f_n).__code__.co_argcount]
            ]
            for f_n in [
                func for func in dir(DNSAuthenticatorService)
                if callable(getattr(DNSAuthenticatorService, func))
                and func.startswith('update_txt_record_')
            ]
        }

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
            Dict('attributes', additional_attrs=True)
        )
    )
    async def do_create(self, data):
        await self.common_validation(data, 'dns_authenticator_create')

        id = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
        )

        return await self._get_instance(id)

    @accepts(
        Int('id', required=True),
        Dict('attributes', additional_attrs=True, required=True)
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new['attributes'].update(data)

        await self.common_validation(data, 'dns_authenticator_update')

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
            Str('key', required=True),
            Str('domain', required=True),
            Str('challenge', required=True)
        )
    )
    def update_txt_record(self, data):

        authenticator = self.middleware.call_sync('dns.authenticator._get_instance', data['authenticator'])

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
    4) In case update_txt_record is unsuccessful, ValidationErrors should be RAISED with appropriate
       status/reason.
    '''

    def update_txt_record_route53(self, domain, challenge, key, access_key_id, secret_access_key):
        session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key
        )
        client = session.client('route53')
        verrors = ValidationErrors()

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
                verrors.add(
                    'dns_authenticator_update_record.domain',
                    f'Unable to find a Route53 hosted zone for {domain}'
                )
        except boto_exceptions.ClientError as e:
            verrors.add(
                'dns_authenticator_update_record.credentials',
                f'Failed to get Hosted zones with provided credentials :{e}'
            )

        if verrors:
            raise verrors

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
            verrors.add(
                'dns_authenticator_update_record.credentials',
                f'Failed to update record sets : {e}'
            )

            raise verrors

        """
        Wait for a change to be propagated to all Route53 DNS servers.
        https://docs.aws.amazon.com/Route53/latest/APIReference/API_GetChange.html
        """
        for unused_n in range(0, 120):
            r = client.get_change(Id=resp['ChangeInfo']['Id'])
            if r['ChangeInfo']['Status'] == 'INSYNC':
                return resp['ChangeInfo']['Id']
            time.sleep(5)

        verrors.add(
            'dns_authenticator_update_record.domain',
            f'Timed out waiting for Route53 change. Current status: {resp["ChangeInfo"]["Status"]}'
        )

        raise verrors
