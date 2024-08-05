from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

API_KEY_NAME = 'AUDIT_API_KEY'


def test_api_key_audit():
    payload = {'name': AUDIT_API_KEY, 'allowlist': [{'resource': '*', 'method': '*'}]}
    payload2 = {'allowlist': []}

    try:
        with expect_audit_method_calls([{
            'method': 'api_key.create',
            'params': [payload],
            'description': f'Create API key {API_KEY_NAME}',
        }]):
            call('api_key.create', payload)

        with expect_audit_method_calls([{
            'method': 'api_key.update',
            'params': [API_KEY_NAME, payload2],
            'description': f'Update API key {API_KEY_NAME}',
        }]):
            call('api_key.update', API_KEY_NAME, payload2)

    finally:
        with expect_audit_method_calls([{
            'method': 'api_key.delete',
            'params': [API_KEY_NAME],
            'description': f'Delete API key {API_KEY_NAME}',
        }]):
            call('api_key.delete', API_KEY_NAME)
