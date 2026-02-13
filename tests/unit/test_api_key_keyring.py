import pytest
import truenas_pyscram
from base64 import b64decode
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
        assert resp['response_type'] == 'SCRAM_RESPONSE', str(resp)
        assert resp['scram_type'] == 'SERVER_FIRST_RESPONSE', str(resp)
        server_first_response = truenas_pyscram.ServerFirstMessage(rfc_string=resp['rfc_str'])

        client_final_message = truenas_pyscram.ClientFinalMessage(
            client_first=client_first_message,
            server_first=server_first_response,
            client_key=truenas_pyscram.CryptoDatum(b64decode(root_api_key['client_key'])),
            stored_key=truenas_pyscram.CryptoDatum(b64decode(root_api_key['stored_key'])),
        )

        resp = c.call('auth.login_ex', {
            'mechanism': 'SCRAM',
            'scram_type': 'CLIENT_FINAL_MESSAGE',
            'rfc_str': str(client_final_message),
        })
        assert resp['response_type'] == 'SCRAM_RESPONSE', str(resp)
        assert resp['scram_type'] == 'SERVER_FINAL_RESPONSE', str(resp)

        server_final_response = truenas_pyscram.ServerFinalMessage(rfc_string=resp['rfc_str'])

        # This will raise an exception if server signature incorrect
        truenas_pyscram.verify_server_signature(
            client_first=client_first_message,
            client_final=client_final_message,
            server_first=server_first_response,
            server_final=server_final_response,
            server_key=truenas_pyscram.CryptoDatum(b64decode(root_api_key['server_key']))
        )


def test__convert_raw_key_valid(root_api_key):
    """Test converting a valid raw API key to SCRAM components."""
    with Client() as c:
        result = c.call('api_key.convert_raw_key', root_api_key['key'])

    # Verify all expected fields are present
    assert result['api_key_id'] == root_api_key['id']
    assert 'iterations' in result
    assert 'salt' in result
    assert 'client_key' in result
    assert 'stored_key' in result
    assert 'server_key' in result

    # Verify the SCRAM data matches the original
    assert result['iterations'] == root_api_key['iterations']
    assert result['salt'] == root_api_key['salt']
    assert result['client_key'] == root_api_key['client_key']
    assert result['stored_key'] == root_api_key['stored_key']
    assert result['server_key'] == root_api_key['server_key']


def test__convert_raw_key_invalid_format():
    """Test that invalid raw key format is rejected."""
    with Client() as c:
        # Missing hyphen separator
        with pytest.raises(Exception, match='Not a valid raw API key'):
            c.call('api_key.convert_raw_key', '123invalidkey')

        # Non-numeric ID
        with pytest.raises(Exception, match='Not a valid raw API key'):
            c.call('api_key.convert_raw_key', 'abc-validkeydata' + 'x' * 51)

        # Empty string (caught by pydantic NonEmptyString validation)
        with pytest.raises(Exception, match='String should have at least 1 character'):
            c.call('api_key.convert_raw_key', '')


def test__convert_raw_key_wrong_size():
    """Test that keys with incorrect size are rejected by regex pattern."""
    with Client() as c:
        # Key too short (63 chars instead of 64) - caught by regex pattern
        with pytest.raises(Exception, match='Not a valid raw API key'):
            c.call('api_key.convert_raw_key', '123-' + 'a' * 63)

        # Key too long (65 chars instead of 64) - caught by regex pattern
        with pytest.raises(Exception, match='Not a valid raw API key'):
            c.call('api_key.convert_raw_key', '123-' + 'a' * 65)


def test__convert_raw_key_nonexistent():
    """Test that non-existent key ID is rejected."""
    with Client() as c:
        # Use a very high ID that's unlikely to exist
        with pytest.raises(Exception, match='Key does not exist'):
            c.call('api_key.convert_raw_key', '999999999-' + 'a' * 64)


def test__convert_raw_key_invalid_id():
    """Test that invalid key IDs are rejected."""
    with Client() as c:
        # Zero ID
        with pytest.raises(Exception, match='Invalid key id'):
            c.call('api_key.convert_raw_key', '0-' + 'a' * 64)

        # Negative ID
        with pytest.raises(Exception, match='Not a valid raw API key'):
            c.call('api_key.convert_raw_key', '-1-' + 'a' * 64)


def test__convert_raw_key_revoked():
    """Test that revoked keys are rejected."""
    # Create a temporary key and revoke it
    with Client() as c:
        temp_key = c.call('api_key.create', {
            'username': 'root',
            'name': 'TEMP_REVOKED_KEY_TEST'
        })

    try:
        with Client() as c:
            # Revoke the key
            c.call('datastore.update', 'account.api_key', temp_key['id'], {
                'expiry': -1,
                'revoked_reason': 'Test revocation'
            })

            # Try to convert the revoked key
            with pytest.raises(Exception, match='Key is revoked'):
                c.call('api_key.convert_raw_key', temp_key['key'])
    finally:
        # Clean up
        with Client() as c:
            c.call('api_key.delete', temp_key['id'])


def test__convert_raw_key_whitespace_handling(root_api_key):
    """Test that leading/trailing whitespace is handled correctly."""
    with Client() as c:
        # Test with leading whitespace
        result = c.call('api_key.convert_raw_key', '  ' + root_api_key['key'])
        assert result['api_key_id'] == root_api_key['id']

        # Test with trailing whitespace
        result = c.call('api_key.convert_raw_key', root_api_key['key'] + '  ')
        assert result['api_key_id'] == root_api_key['id']

        # Test with both
        result = c.call('api_key.convert_raw_key', '  ' + root_api_key['key'] + '  ')
        assert result['api_key_id'] == root_api_key['id']
