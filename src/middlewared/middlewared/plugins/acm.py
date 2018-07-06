import josepy as jose
import json
import requests

from middlewared.schema import Bool, Dict, Int, List, Ref, Str, ValidationErrors
from middlewared.service import accepts, CRUDService

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

    @accepts(
        Dict(
            'acme_create',
            Bool('tos', default=False),
            Int('csr_id', required=True),
            Str('directory_uri', required=True),
            Str('name', required=True)
        )
    )
    def do_create(self, data):
        verrors = ValidationErrors()

        csr_data = self.middleware.call_sync(
            'certificate.query',
            ['id', '=', data['csr_id']]
        )

        if not csr_data:
            verrors.add(
                'acme.csr_id',
                'Specified CSR does not exist on FreeNAS system'
            )
        elif not csr_data[0]['CSR']:
            verrors.add(
                'acme.csr_id',
                'Please provide a valid CSR id'
            )
        else:
            csr_data = csr_data[0]

        if verrors:
            raise verrors

        acme_client, key = get_acme_client_and_key(self.middleware, data['directory_uri'], data['tos'])
        # perform operations and have a cert issued

        order = acme_client.new_order(csr_data['CSR'])
        challenge = None
        for chg in order.authorizations[0].body.challenges:
            if chg.typ == 'dns-01':
                challenge = chg

        token = challenge.validation(key)
        # FOR NOW ASSUMING THAT WE ONLY HAVE COMMON NAME IN CSR AND NO SAN values

        domains = [csr_data['common']]
        for domain in domains:
            pass

    def handle_authorizations(self, order, domain_names):
        # For multiple domain providers in domain names, I think we should ask the end user to specify which domain
        # provider is used for which domain so authorizations can be handled gracefully
        # https://serverfault.com/questions/906407/lets-encrypt-dns-challenge-with-multiple-public-dns-providers
        pass



class DNSAuthenticatorService(CRUDService):

    class Config:
        namespace = 'dns.authenticator'
        datastore = 'system.dnsauthenticator'
        datastore_prefix = 'dns_'
        datastore_extend = 'dns.authenticator.authenticator_extend'

    async def authenticator_extend(self, data):
        data['keys'] = {
            key: value for obj in
            await self.middleware.call(
                'datastore.query',
                'system.dnsauthenticatorcredentials',
                [['authenticator', '=', data['id']]],
                {'prefix': 'dns_credentials_'}
            ) for key, value in obj.items() if key != 'id'
        }
        return data

    # FIXME: THIS SHOULD BE REMOVED AND FREENAS CLOUD CREDENTIALS BE USED INSTEAD
    @accepts(
        Dict(
            'dns_authenticator_create',
            Str('service', required=True),
            List('keys', items=[Dict(
                'dns_authenticator_credential',
                Str('key', required=True),
                Str('value', required=True),
                register=True
            )], default=[])
        )
    )
    async def do_create(self, data):
        id = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            {'authenticator': data['service']},
            {'prefix': self._config.datastore_prefix}
        )
        for credential_pair in data['keys']:
            await self.middleware.call(
                'datastore.insert',
                'system.dnsauthenticatorcredentials',
                {'key': credential_pair['key'], 'value': credential_pair['value'], 'authenticator': id},
                {'prefix': 'dns_credentials_'}
            )

        return self._get_instance(id)

    @accepts(
        Int('id', required=True),
        List('keys', items=[Ref('dns_authenticator_credential')], required=True)
    )
    async def do_update(self, id, data):
        # If a key is provided which does not exist before, for now we will not insert that key in db
        # only existing keys values would be updated
        for credential_pair in data:
            key_id = await self.middleware.call(
                'datastore.query',
                'system.dnsauthenticatorcredentials',
                [
                    ['key', '=', credential_pair['key']],
                    ['authenticator', '=', id],
                    ['value', '!=', credential_pair['value']]
                 ],
                {'prefix': 'dns_credentials_'}
            )
            if key_id:
                await self.middleware.call(
                    'datastore.update',
                    'system.dnsauthenticatorcredentials',
                    key_id[0]['id'],
                    {'value': credential_pair['value']},
                    {'prefix': 'dns_credentials_'}
                )

        return self._get_instance(id)

    @accepts(
        Int('id', required=True)
    )
    async def do_delete(self, id):
        for key_id in [o['id'] for o in
            await self.middleware.call(
                'datastore.query', 'system.dnsauthenticatorcredentials',
                [['authenticator', '=', id]]
            )
        ]:
            await self.middleware.call(
                'datastore.delete',
                'system.dnsauthenticatorcredentials',
                key_id
            )

        return await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

    def update_txt_record(self, authenticator_service, txt_record):
        verrors = ValidationErrors()

        authenticator = self.middleware.call_sync(
            'dns.authenticator.query',
            [['authenticator', '=', authenticator_service]]
        )

        if not authenticator:
            verrors.add(
                'dns_authenticator_update_record.authenticator',
                'Please provide a valid authenticator service'
            )
        else:
            authenticator = authenticator[0]

        if verrors:
            raise verrors

        return self.__getattribute__(
            f'update_txt_record_{authenticator_service}'
        )(txt_record, authenticator['keys'])  # THIS SHOULD BE GOOD - test this please

    def update_txt_record_aws(self, txt_record, credentials):
        # waiting for access keys to test boto record updates
        import time
        time.sleep(5*60)
