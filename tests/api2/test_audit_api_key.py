import datetime

from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

API_KEY_NAME = 'AUDIT_API_KEY'


def test_api_key_audit():
    payload = {'username': 'root', 'name': API_KEY_NAME}
    payload2 = {'expires_at': None}
    api_key_id = None

    try:
        with expect_audit_method_calls([{
            'method': 'api_key.create',
            'params': [payload],
            'description': f'Create API key {API_KEY_NAME}',
        }]):
            api_key = call('api_key.create', payload)
            api_key_id = api_key['id']

            # Set expiration 60 minutes in future
            payload2['expires_at'] = api_key['created_at'] + datetime.timedelta(minutes=60)

        with expect_audit_method_calls([{
            'method': 'api_key.update',
            'params': [api_key_id, payload2],
            'description': f'Update API key {API_KEY_NAME}',
        }]):
            call('api_key.update', api_key_id, payload2)

    finally:
        if api_key_id:
            with expect_audit_method_calls([{
                'method': 'api_key.delete',
                'params': [api_key_id],
                'description': f'Delete API key {API_KEY_NAME}',
            }]):
                call('api_key.delete', api_key_id)
