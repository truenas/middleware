import josepy as jose
import json

from acme import client, messages

from middlewared.service import Service


class ACMEService(Service):

    class Config:
        namespace = 'acme'
        private = True

    def get_acme_client_and_key(self, acme_directory_uri, tos=False):
        data = self.middleware.call_sync('acme.registration.query', [['directory', '=', acme_directory_uri]])
        if not data:
            data = self.middleware.call_sync(
                'acme.registration.create',
                {'tos': tos, 'acme_directory_uri': acme_directory_uri}
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
                    'kty': 'RSA',
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
