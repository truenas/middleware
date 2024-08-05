from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

API_KEY_NAME = 'AUDIT_API_KEY'


def test_api_key_audit():
    payload = {'name': API_KEY_NAME, 'allowlist': [{'resource': '*', 'method': '*'}]}
    payload2 = {'allowlist': []}
    audit_id = None

    try:
        with expect_audit_method_calls([{
            'method': 'api_key.create',
            'params': [payload],
            'description': f'Create API key {API_KEY_NAME}',
        }]):
            api_key_id = call('api_key.create', payload)['id']

        with expect_audit_method_calls([{
            'method': 'api_key.update',
            'params': [api_key_id, payload2],
            'description': f'Update API key {API_KEY_NAME}',
        }]):
            call('api_key.update', api_key_id, payload2)

    finally:
        if audit_id:
            with expect_audit_method_calls([{
                'method': 'api_key.delete',
                'params': [api_key_id],
                'description': f'Delete API key {API_KEY_NAME}',
            }]):
                call('api_key.delete', api_key_id)
