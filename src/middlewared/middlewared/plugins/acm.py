import boto3
import datetime
import josepy as jose
import json
import pytz
import requests
import time

from middlewared.plugins.crypto import CERT_TYPE_EXISTING, RE_CERTIFICATE
from middlewared.schema import Bool, Dict, Int, Str, ValidationErrors
from middlewared.service import accepts, CRUDService, private
from middlewared.validators import validate_attributes

from acme import client
from acme import messages
from certbot import achallenges
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from pprint import pprint


def get_acme_client_and_key(middleware, directory_uri, tos=False):
    data = middleware.call_sync('acme.registration.query', [['directory', '=', directory_uri]])
    if not data:
        data = middleware.call_sync(
            'acme.registration.create',
            {'tos': tos, 'directory_uri': directory_uri}
        )
    else:
        data = data[0]
    # Making key now
    key = jose.JWKRSA.fields_from_json(json.loads(data['body']['key']))
    key_dict = key.fields_to_partial_json()
    # Making registration resource now
    registration = messages.RegistrationResource.from_json({
        'uri': data['uri'],
        'terms_of_service': data['tos'],
        'body': {
            'contact': [data['body']['contact']],
            'status': data['body']['status'],
            'key': {
                'e': key_dict['e'],
                'kty': 'RSA',  # TODO: IS THE HARD CODED VALUE IDEAL ?
                'n': key_dict['n']
            }
        }
    })

    return client.ClientV2(
        messages.Directory({
            'newAccount': data['new_account_uri'],
            'newNonce': data['new_nonce_uri'],
            'newOrder': data['new_order_uri'],
            'revokeCert': data['revoke_cert_uri']
        }),
        client.ClientNetwork(key, account=registration)
    ), key


class ACMERegistrationService(CRUDService):

    class Config:
        datastore = 'system.acmeregistration'
        datastore_extend = 'acme.registration.register_extend'
        namespace = 'acme.registration'
        #TODO: ADD PRIVATE TO TRUE

    async def register_extend(self, data):
        data['body'] = {
            key: value for key, value in
            (await self.middleware.call(
                'datastore.query', 'system.acmeregistrationbody',
                [['acme', '=', data['id']]], {'get': True}
            )).items() if key != 'acme'
        }
        return data

    def get_directory(self, directory_uri):
        try:
            response = requests.get(directory_uri).json()
            return messages.Directory({
                key: response[key] for key in ['newAccount', 'newNonce', 'newOrder', 'revokeCert']
            })
        except (requests.ConnectionError, requests.Timeout, json.JSONDecodeError, KeyError) as e:
            return str(e)

    @accepts(
        Dict(
            'acme_registration_create',
            Bool('tos', default=False),
            Dict(
                'JWK_create',
                Int('key_size', default=2048),
                Int('public_exponent', default=65537)
            ),
            Str('directory_uri', required=True),
        )
    )
    def do_create(self, data):
        # NOTE: FOR NOW THE DEFAULTS FOR JWK_create SHOULD NOT BE TAMPERED WITH AS THEIR IS A LIMIT TO THE KEY SIZE
        #  WHICH WE SAVE IN DATABASE
        # STEPS FOR CREATION
        # 1) CREATE KEY
        # 2) REGISTER CLIENT
        # 3) SAVE KEY
        # 4) SAVE REGISTRATION OBJECT
        # 5) SAVE REGISTRATION BODY

        verrors = ValidationErrors()

        directory = self.get_directory(data['directory_uri'])
        if not directory:
            verrors.add(
                'acme_registration_create.direcotry_uri',
                f'System was unable to retrieve the directory with the specified directory_uri: {directory}'
            )

        if not data['tos']:
            verrors.add(
                'acme_registration_create.tos',
                'Please agree to the terms of service'
            )

        email = (self.middleware.call_sync('user.query', [['id', '=', 1]]))[0]['email']
        if not email:
            verrors.add(
                'acme_registration_create.email',
                'Please specify root email address which will be used with the ACME server'
            )

        if self.middleware.call_sync('acme.registration.query', [['directory', '=', data['directory_uri']]]):
            verrors.add(
                'acme_registration_create.directory',
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
                'directory': data['directory_uri']  # handle trailing / ?
            },
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

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        return response


class ACMEService(CRUDService):

    class Config:
        datastore = 'system.certificate'
        datastore_prefix = 'cert_'
        datastore_extend = 'acme.cert_extend'

    @private
    async def get_domain_names(self, data):
        names = [data['common']]
        names.extend(data['san'])
        return names

    def issue_certificate(self, data, csr_data):
        verrors = ValidationErrors()

        # For now, lets only allow dns validation for dns providers we have an authenticator plugin for

        domains = self.middleware.call_sync('acme.get_domain_names', csr_data)
        print('we have order\n\n')
        dns_authenticator_ids = [o['id'] for o in self.middleware.call_sync('dns.authenticator.query')]
        for domain in domains:
            if domain not in data['domain_dns_mapping']:
                verrors.add(
                    'acme_create.domain_dns_mapping',
                    f'Please provide DNS authenticator id for {domain}'
                )
            elif data['domain_dns_mapping'][domain] not in dns_authenticator_ids:
                verrors.add(
                    'acme_create.domain_dns_mapping',
                    f'Please provide valid DNS Authenticator id for {domain}'
                )
        for domain in data['domain_dns_mapping']:
            if domain not in domains:
                verrors.add(
                    'acme_create.domain_dns_mapping',
                    f'{domain} not specified in the CSR'
                )

        if verrors:
            raise verrors

        acme_client, key = get_acme_client_and_key(self.middleware, data['directory_uri'], data['tos'])
        # perform operations and have a cert issued
        print('\n\nwe have client')
        order = acme_client.new_order(csr_data['CSR'])

        self.handle_authorizations(order, data['domain_dns_mapping'], acme_client, key)

        print('\n\nauthorizations handled')

        # Polling for a maximum of 10 minutes while trying to finalize order
        # Should we try .poll() instead first ? research please
        return acme_client.poll_and_finalize(order, datetime.datetime.now() + datetime.timedelta(minutes=10))

    @accepts(
        Dict(
            'acme_create',
            Bool('tos', default=False),
            Int('csr_id', required=True),
            Str('directory_uri', required=True),
            Str('name', required=True),
            Dict('domain_dns_mapping', additional_attrs=True, required=True)
        )
    )
    def do_create(self, data):
        # TODO: THIS SHOULD BE A JOB ?

        verrors = ValidationErrors()

        csr_data = self.middleware.call_sync(
            'certificate.query',
            [['id', '=', data['csr_id']]]
        )

        if self.middleware.call_sync(
            'certificate.query',
            [['name', '=', data['name']]]
        ):
            verrors.add(
                'acme_create.name',
                'A Certificate with this name already exists'
            )

        if not csr_data:
            verrors.add(
                'acme_create.csr_id',
                'Specified CSR does not exist on FreeNAS system'
            )
        elif not csr_data[0]['CSR']:
            verrors.add(
                'acme_create.csr_id',
                'Please provide a valid CSR id'
            )
        else:
            csr_data = csr_data[0]

        if verrors:
            raise verrors

        final_order = self.issue_certificate(data, csr_data)

        print('\n\n')
        pprint(json.loads(final_order.json_dumps()))

        cert_dict = {
            'acme': self.middleware.call_sync(
                        'acme.registration.query',
                        [['directory', '=', data['directory_uri']]]
                    )[0]['id'],
            'acme_uri': final_order.uri,
            'certificate': final_order.fullchain_pem,
            'CSR': csr_data['CSR'],
            'privatekey': csr_data['privatekey'],
            'name': data['name'],
            'expire': final_order.body.expires.astimezone(pytz.utc).strftime("%Y-%m-%d"),
            'chain': True if len(RE_CERTIFICATE.findall(final_order.fullchain_pem)) > 1 else False,
            'type': CERT_TYPE_EXISTING,
            'domain_authenticators': data['domain_dns_mapping']
        }

        for key, value in (self.middleware.call_sync(
            'certificate.load_certificate', final_order.fullchain_pem
        )).items():
            cert_dict[key] = value

        # save cert and other useful attributes
        cert_id = self.middleware.call_sync(
            'datastore.insert',
            self._config.datastore,
            cert_dict, {
                'prefix': self._config.datastore_prefix
            }
        )

        self.middleware.call_sync(
            'service.start',
            'ix-ssl',
            {'onetime': False}
        )

        return self.middleware.call_sync(
            'certificate.query',
            [['id', '=', cert_id]], {
                'get': True
            }
        )

    # TODO: THIS SHOULD BE A JOB ?
    def handle_authorizations(self, order, domain_names_dns_mapping, acme_client, key):
        # When this is called, it should be ensured by the function calling this function that for all authorization
        # resource, a domain name dns mapping is available ? Ideal ?
        # For multiple domain providers in domain names, I think we should ask the end user to specify which domain
        # provider is used for which domain so authorizations can be handled gracefully
        # https://serverfault.com/questions/906407/lets-encrypt-dns-challenge-with-multiple-public-dns-providers
        verrors = ValidationErrors()

        for authorization_resource in order.authorizations:
            domain = authorization_resource.body.identifier.value  # TODO: handle wildcards
            challenge = None
            for chg in authorization_resource.body.challenges:
                if chg.typ == 'dns-01':
                    challenge = chg

            if not challenge:
                verrors.add(
                    'acme_authorization.domain',
                    f'DNS Challenge not found for domain {authorization_resource.body.identifier.value}'
                )

                raise verrors

            token = challenge.validation(key)

            print('\n\nTOKEN - ', token)

            self.middleware.call_sync(
                'dns.authenticator.update_txt_record', {
                    'authenticator': domain_names_dns_mapping[domain],
                    'challenge': challenge.json_dumps(),
                    'domain': domain,
                    'key': key.json_dumps()
                }
            )

            acme_client.answer_challenge(challenge, challenge.response(key))
            print('\nchallenge answered')


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
                f'FreeNAS does not support {data["authenticator"]} as an Authenticator'
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
        verrors = ValidationErrors()

        authenticator = self.middleware.call_sync(
            'dns.authenticator.query',
            [['id', '=', data['authenticator']]]
        )

        if not authenticator:
            verrors.add(
                'dns_authenticator_update_record.authenticator',
                f'{data["authenticator"]} not a valid authenticator Id'
            )
        else:
            authenticator = authenticator[0]

        if verrors:
            raise verrors

        return self.__getattribute__(
            f'update_txt_record_{authenticator["authenticator"].lower()}'
        )(
            data['domain'],
            messages.ChallengeBody.from_json(json.loads(data['challenge'])),
            jose.JWKRSA.fields_from_json(json.loads(data['key'])),
            **authenticator['attributes']
        )  # THIS SHOULD BE GOOD - test this please

    def update_txt_record_route53(self, domain, challenge, key, access_key_id, secret_access_key):
        session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key
        )
        # TODO: HANDLE CREDENTIAL OR REQUEST ERRORS GRACEFULLY
        client = session.client('route53')
        verrors = ValidationErrors()

        # Finding zone id for the given domain
        paginator = client.get_paginator('list_hosted_zones')
        target_labels = domain.rstrip('.').split('.')
        zones = []
        for page in paginator.paginate():
            for zone in page["HostedZones"]:
                if zone["Config"]["PrivateZone"]:
                    continue

                candidate_labels = zone["Name"].rstrip(".").split(".")
                if candidate_labels == target_labels[-len(candidate_labels):]:
                    zones.append((zone["Name"], zone["Id"]))
        if not zones:
            verrors.add(
                'dns_authenticator_update_record.domain',
                f'Unable to find a Route53 hosted zone for {domain}'
            )

            raise verrors

        # Order the zones that are suffixes for our desired to domain by
        # length, this puts them in an order like:
        # ["foo.bar.baz.com", "bar.baz.com", "baz.com", "com"]
        # And then we choose the first one, which will be the most specific.
        zones.sort(key=lambda z: len(z[0]), reverse=True)
        zone_id = zones[0][1]

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
                'Comment': 'FreeNAS-dns-route53 certificate validation'
            }
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

        verrors.add(
            'dns_authenticator_update_record.domain',
            f'Timed out waiting for Route53 change. Current status: {resp["ChangeInfo"]["Status"]}'
        )

        raise verrors
