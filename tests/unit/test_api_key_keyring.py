import pytest
import truenas_pyscram
from truenas_api_client import Client


@pytest.fixture(scope='module')
def root_api_key():
    with Client() as c:
        api_key = c.call('api_key.create', {'username': 'root', 'name': 'ROOT_TEST_KEYRING'})

    try:
        yield api_key
    finally:
        with Client() as c:
            c.call('api_key.delete', api_key['id'])



def test__check_keys(root_api_key):
    # Client info should be in create response
    assert 'client_key' in root_api_key
    assert 'key' in root_api_key

    with Client() as c:
        on_disk = c.call('api_key.get_instance', root_api_key['id'])

    # Client info should *not* be stored on disk
    assert 'client_key' not in on_disk
    assert 'key' not in on_disk


def test__api_key_legacy(root_api_key):
    with Client('ws://127.0.0.1/api/current') as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'API_KEY_PLAIN',
            'username': 'root',
            'api_key': root_api_key['key']
        })

        assert resp['response_type'] == 'SUCCESS', str(resp)


def test__api_key_scram(root_api_key):
    with Client('ws://127.0.0.1/api/current') as c:
        client_first_message = truenas_pyscram.ClientFirstMessage(
            username=root_api_key['username'],
            api_key_id=root_api_key['id'],
        )
        resp = c.call('auth.login_ex', {
            'mechanism': 'SCRAM',
            'scram_type': 'CLIENT_FIRST_MESSAGE',
            'rfc_str': str(client_first_message),
        })
        assert resp['response_type'] == 'SUCCESS', str(resp)

