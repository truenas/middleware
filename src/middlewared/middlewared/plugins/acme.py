import josepy as jose
import json
import requests

from middlewared.schema import Bool, Dict, Int, Str, ValidationErrors
from middlewared.service import accepts, CRUDService

from acme import client
from acme import messages
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa


class ACMERegistrationService(CRUDService):

    ACME_CLIENT = None

    class Config:
        datastore = 'system.acmeregistration'
        datastore_extend = 'acme.registration.register_extend'
        datastore_prefix = 'acme_'
        namespace = 'acme.registration'
        #TODO: ADD PRIVATE TO TRUE

    async def register_extend(self, data):
        return data

    # OVERRIDE query method of base class and set the ACME CLIENT object if a match is found and a param says like

    async def query(self, filters=None, options=None):
        if not options:
            options = {}

        result = None  # query object
        if result and all(options.get(k) for k in ['set_client', 'get']):

            ACMERegistrationService.ACME_CLIENT = None  # set client here

        return result

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

        # Save key
        key_id = self.middleware.call_sync(
            'datastore.insert',
            'system.jwkrsakey',
            {'jwk_' + key: value for key, value in json.loads(key.json_dumps()).items()}
        )

        # Save registration body
        registration_body_id = self.middleware.call_sync(
            'datastore.insert',
            'system.acmeregistrationBody',
            {
                'contact': register.body.contact[0],
                'status': register.body.status,
                'key': key_id
            },
            {'prefix': 'registration_body_'}
        )

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
                'body': registration_body_id,
                'directory': data['directory_uri']
            },
            {'prefix': self._config.datastore_prefix}
        )

        # Change this ?
        ACMERegistrationService.ACME_CLIENT = acme_client
        return self.middleware.call_sync(f'{self._config.namespace}.query', [('id', '=', id)])[0]


class ACMEService(CRUDService):

    class Config:
        datastore = 'system.certificate'
        datastore_prefix = 'cert_'

    @accepts(
        Dict(
            'acme_create',
            Int('csr_id', required=True),
            Str('directory_uri', required=True)
        )
    )
    def do_create(self, data):
        # query registration objects with directory url to see if a registration exists, if yes, take the acme client
        # like
        if not self.middleware.call_sync(
                'acme.registration.query',
                [['directory', '=', data['directory_uri']]],
                {'get': True, 'set_client': True}  # There are a few bugs in the get approach, but this is just an idea
                                                   # to show how acme client could work
        ):
            # create registration here
            pass
        acme_client = ACMERegistrationService.ACME_CLIENT
        # perform operations and have a cert issued
        pass



if __name__ == '__main__':


    BITS = 2048
    key = jose.JWKRSA(key=rsa.generate_private_key(
        public_exponent=65537,
        key_size=BITS,
        backend=default_backend()))
    DIRECTORY_URL = 'https://acme-staging.api.letsencrypt.org/directory'
    DIRECTORY_URL = 'https://acme-staging-v02.api.letsencrypt.org/directory'
    #DIRECTORY_URL = 'https://acme-v02.api.letsencrypt.org/directory'
    domain = 'acmedev.agencialivre.com.br'
    dir = messages.Directory({'newAccount': DIRECTORY_URL})
    DIRECTORY_V2 = messages.Directory({
        'newAccount': 'https://acme-staging-v02.api.letsencrypt.org/acme/new-acct',
        'newNonce': 'https://acme-staging-v02.api.letsencrypt.org/acme/new-nonce',
        'newOrder': 'https://acme-staging-v02.api.letsencrypt.org/acme/new-order',
        'revokeCert': 'https://acme-staging-v02.api.letsencrypt.org/acme/revoke-cert',
    })
    acme = client.ClientV2(DIRECTORY_V2, client.ClientNetwork(key))
    regr = acme.new_account(messages.NewRegistration.from_data(email='waqar@ixsystems.com', terms_of_service_agreed=True))
    print(regr)
