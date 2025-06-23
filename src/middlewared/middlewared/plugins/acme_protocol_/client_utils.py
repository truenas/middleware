import json
import typing

import josepy as jose
from acme import client, messages


class BodyDict(typing.TypedDict):
    status: str
    key: str


class ACMEClientAndKeyData(typing.TypedDict):
    uri: str
    tos: bool | str
    new_account_uri: str
    new_nonce_uri: str
    new_order_uri: str
    revoke_cert_uri: str
    body: BodyDict


def get_acme_client_and_key(data: ACMEClientAndKeyData) -> tuple[client.ClientV2, jose.JWKRSA]:
    """
    Expected data dict should contain the following
    - uri: str
    - tos: bool | str
    - new_account_uri: str
    - new_nonce_uri: str
    - new_order_uri: str
    - revoke_cert_uri: str
    - body: dict
        - status: str
        - key: dict
            - e: str
            - n
    """

    # Making key now
    key = jose.JWKRSA.fields_from_json(json.loads(data['body']['key']))
    key_dict = key.fields_to_partial_json()
    # Making registration resource now
    registration = messages.RegistrationResource.from_json({
        'uri': data['uri'],
        'terms_of_service': data['tos'],
        'body': {
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
