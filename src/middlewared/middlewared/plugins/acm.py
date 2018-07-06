import datetime
import josepy as jose
import json
import requests

from middlewared.schema import Bool, Dict, Int, List, Ref, Str, ValidationErrors
from middlewared.service import accepts, CRUDService, Service

from acme import client
from acme import messages
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
        datastore_prefix = 'acme_'
        namespace = 'acme.registration'
        #TODO: ADD PRIVATE TO TRUE

    async def register_extend(self, data):
        data['body'] = {
            key: value for key, value in
            (await self.middleware.call(
                'datastore.query', 'system.acmeregistrationbody',
                [['acme', '=', data['id']]], {'prefix': 'registration_body_', 'get': True}
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
            {'prefix': self._config.datastore_prefix}
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
            {'prefix': 'registration_body_'}
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

    @accepts()
    async def supported_dns_authenticators(self):
        return [
            'ROUTE53'
        ]

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
        #TODO: THIS SHOULD BE A JOB ?
        verrors = ValidationErrors()

        csr_data = self.middleware.call_sync(
            'certificate.query',
            [['id', '=', data['csr_id']]]
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

        acme_client, key = get_acme_client_and_key(self.middleware, data['directory_uri'], data['tos'])
        # perform operations and have a cert issued
        print('\n\nwe have client')
        order = acme_client.new_order(csr_data['CSR'])

        # For now, lets only allow dns validation for dns providers we have an authenticator plugin for

        domains = [csr_data['common']]
        domains.extend(csr_data['san'])
        print('we have order\n\n')
        CLOUD_PROVIDER_LIST = ['ROUTE53']  # We can query this from cloudsync.providers / acme.supported_dns_authenticators
                                           # For now assuming that we will use the first credentials we find for
                                           # cloudsync.provider
        for domain in domains:
            if domain not in data['domain_dns_mapping']:
                verrors.add(
                    'acme_create.domain_dns_mapping',
                    f'Please provide DNS authenticator for {domain}'
                )
            elif data['domain_dns_mapping'][domain].lower() not in [v.lower() for v in CLOUD_PROVIDER_LIST]:
                verrors.add(
                    'acme_create.domain_dns_mapping',
                    f'Please provide valid DNS Authenticator for {domain}'
                )

        if verrors:
            raise verrors

        self.handle_authorizations(order, data['domain_dns_mapping'], acme_client, key)

        print('\n\nauthorizations handled')

        # Polling for a maximum of 10 minutes while trying to finalize order
        # Should we try .poll() instead first ? research please
        final_order = acme_client.poll_and_finalize(order, datetime.datetime.now() + datetime.timedelta(minutes=10))

        cert_chain = final_order.fullchain_pem
        pprint(cert_chain)
        pprint(json.loads(final_order.json_dumps()))

        # save cert and other useful attributes
        return True

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
                    'authenticator_service': domain_names_dns_mapping[domain],
                    'txt_record': token,
                    'domain': domain
                }
            )

            acme_client.answer_challenge(challenge, challenge.response(key))
            print('\nchallenge answered')


class DNSAuthenticatorService(Service):

    class Config:
        namespace = 'dns.authenticator'

    @accepts(
        Dict(
            'update_txt_record',
            Str('authenticator_service', required=True),
            Str('txt_record', required=True),
            Str('domain', required=True)
        )
    )
    def update_txt_record(self, data):
        verrors = ValidationErrors()

        authenticator = [
            value.lower() for value in self.middleware.call_sync(
                'acme.supported_dns_authenticators',
            )
        ]

        if data['authenticator_service'].lower() not in authenticator:
            verrors.add(
                'dns_authenticator_update_record.authenticator',
                f'{data["authenticator_service"]} not a supported authenticator service'
            )

        if verrors:
            raise verrors

        return self.__getattribute__(
            f'update_txt_record_{data["authenticator_service"].lower()}'
        )(data['txt_record'], data['domain'])  # THIS SHOULD BE GOOD - test this please

    def update_txt_record_route53(self, txt_record, domain):
        # waiting for access keys to test boto record updates
        import time
        print('going to sleep')
        time.sleep(45)
        print('\n\nAWOKE FROM SLEEP')
