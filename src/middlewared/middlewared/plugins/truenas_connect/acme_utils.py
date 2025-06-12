from urllib.parse import urlparse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from josepy import JWKRSA
from jsonschema import validate as jsonschema_validate, ValidationError as JSONValidationError


ACME_CONFIG_JSON_SCHEMA = {
    '$schema': 'http://json-schema.org/draft-07/schema#',
    'type': 'object',
    'properties': {
        'endpoint': {
            'type': 'string',
        },
        'account': {
            'type': 'object',
            'properties': {
                'status': {
                    'type': 'string',
                },
                'uri': {
                    'type': 'string',
                },
                'key': {
                    'type': 'string',
                }
            },
            'required': ['status', 'uri', 'key'],
            'additionalProperties': True,
        }
    },
    'required': ['endpoint', 'account'],
    'additionalProperties': True,
}


def normalize_acme_config(config: dict) -> dict:
    try:
        jsonschema_validate(config['acme_details'], ACME_CONFIG_JSON_SCHEMA)
    except JSONValidationError as e:
        config['error'] = f'Failed to validate ACME config: {e}'
        return config

    acme_details = config['acme_details']
    private_key = serialization.load_pem_private_key(
        acme_details['account']['key'].encode(), password=None, backend=default_backend()
    )
    jwk_rsa = JWKRSA(key=private_key)
    parsed_url = urlparse(f'https://{acme_details["endpoint"]}')
    config['acme_details'] = {
        'uri': acme_details['account']['uri'],
        'directory': acme_details['endpoint'],
        'tos': True,
        'new_account_uri': f'{parsed_url.scheme}://{parsed_url.netloc}/acme/new-acct',
        'new_nonce_uri': f'{parsed_url.scheme}://{parsed_url.netloc}/acme/new-nonce',
        'new_order_uri': f'{parsed_url.scheme}://{parsed_url.netloc}/acme/new-order',
        'revoke_cert_uri': f'{parsed_url.scheme}://{parsed_url.netloc}/acme/revoke-cert',
        'body': {
            'status': acme_details['account']['status'],
            'key': jwk_rsa.json_dumps(),
        }
    }
    return config
