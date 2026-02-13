import json
import os
import pytest
import tempfile
from configparser import ConfigParser

from truenas_api_client import Client


@pytest.fixture(autouse=True)
def clear_ratelimit():
    """Clear rate limit cache before each test to avoid rate limiting."""
    with Client() as c:
        c.call('rate.limit.cache_clear')


@pytest.fixture(scope='module')
def api_key_data():
    """Create an API key and return all its data for testing."""
    with Client() as c:
        api_key = c.call('api_key.create', {
            'username': 'root',
            'name': 'LOGIN_WITH_API_KEY_TEST'
        })

    try:
        yield api_key
    finally:
        with Client() as c:
            c.call('api_key.delete', api_key['id'])


def test__login_with_raw_api_key_string(api_key_data):
    """Test login_with_api_key using raw API key string (format: id-key)."""
    with Client('ws://127.0.0.1/api/current') as c:
        c.login_with_api_key('root', api_key_data['key'])
        me = c.call('auth.me')
        assert me['pw_name'] == 'root'
        assert 'API_KEY' in me['account_attributes']
        assert 'SCRAM' in me['account_attributes']


def test__login_with_raw_api_key_json_file(api_key_data):
    """Test login_with_api_key using JSON file with raw_key field."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({'raw_key': api_key_data['key']}, f)
        f.flush()
        json_file = f.name

    try:
        with Client('ws://127.0.0.1/api/current') as c:
            c.login_with_api_key('root', json_file)
            me = c.call('auth.me')
            assert me['pw_name'] == 'root'
            assert 'API_KEY' in me['account_attributes']
            assert 'SCRAM' in me['account_attributes']
    finally:
        os.unlink(json_file)


def test__login_with_raw_api_key_ini_file(api_key_data):
    """Test login_with_api_key using INI file with raw_key field."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        config = ConfigParser()
        config['TRUENAS_API_KEY'] = {
            'raw_key': api_key_data['key']
        }
        config.write(f)
        f.flush()
        ini_file = f.name

    try:
        with Client('ws://127.0.0.1/api/current') as c:
            c.login_with_api_key('root', ini_file)
            me = c.call('auth.me')
            assert me['pw_name'] == 'root'
            assert 'API_KEY' in me['account_attributes']
            assert 'SCRAM' in me['account_attributes']
    finally:
        os.unlink(ini_file)


def test__login_with_raw_api_key_ini_file_single_section(api_key_data):
    """Test login_with_api_key using INI file with single custom section."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        # Write INI with a single custom section (should auto-select it)
        config = ConfigParser()
        config['API_KEY'] = {
            'raw_key': api_key_data['key']
        }
        config.write(f)
        f.flush()
        ini_file = f.name

    try:
        with Client('ws://127.0.0.1/api/current') as c:
            c.login_with_api_key('root', ini_file)
            me = c.call('auth.me')
            assert me['pw_name'] == 'root'
            assert 'API_KEY' in me['account_attributes']
            assert 'SCRAM' in me['account_attributes']
    finally:
        os.unlink(ini_file)


def test__login_with_precomputed_keys_json_file(api_key_data):
    """Test login_with_api_key using JSON file with precomputed SCRAM keys."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            'client_key': api_key_data['client_key'],
            'stored_key': api_key_data['stored_key'],
            'server_key': api_key_data['server_key'],
            'api_key_id': api_key_data['id']
        }, f)
        f.flush()
        json_file = f.name

    try:
        with Client('ws://127.0.0.1/api/current') as c:
            c.login_with_api_key('root', json_file)
            me = c.call('auth.me')
            assert me['pw_name'] == 'root'
            assert 'API_KEY' in me['account_attributes']
            assert 'SCRAM' in me['account_attributes']
    finally:
        os.unlink(json_file)


def test__login_with_precomputed_keys_ini_file(api_key_data):
    """Test login_with_api_key using INI file with precomputed SCRAM keys."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        config = ConfigParser()
        config['TRUENAS_API_KEY'] = {
            'client_key': api_key_data['client_key'],
            'stored_key': api_key_data['stored_key'],
            'server_key': api_key_data['server_key'],
            'api_key_id': str(api_key_data['id'])
        }
        config.write(f)
        f.flush()
        ini_file = f.name

    try:
        with Client('ws://127.0.0.1/api/current') as c:
            c.login_with_api_key('root', ini_file)
            me = c.call('auth.me')
            assert me['pw_name'] == 'root'
            assert 'API_KEY' in me['account_attributes']
            assert 'SCRAM' in me['account_attributes']
    finally:
        os.unlink(ini_file)


def test__login_with_precomputed_keys_json_string(api_key_data):
    """Test login_with_api_key using JSON string with precomputed SCRAM keys."""
    json_string = json.dumps({
        'client_key': api_key_data['client_key'],
        'stored_key': api_key_data['stored_key'],
        'server_key': api_key_data['server_key'],
        'api_key_id': api_key_data['id']
    })

    with Client('ws://127.0.0.1/api/current') as c:
        c.login_with_api_key('root', json_string)
        me = c.call('auth.me')
        assert me['pw_name'] == 'root'
        assert 'API_KEY' in me['account_attributes']
        assert 'SCRAM' in me['account_attributes']


def test__login_with_raw_api_key_json_string(api_key_data):
    """Test login_with_api_key using JSON string with raw_key field."""
    json_string = json.dumps({'raw_key': api_key_data['key']})

    with Client('ws://127.0.0.1/api/current') as c:
        c.login_with_api_key('root', json_string)
        me = c.call('auth.me')
        assert me['pw_name'] == 'root'
        assert 'API_KEY' in me['account_attributes']
        assert 'SCRAM' in me['account_attributes']


def test__login_with_api_key_auto_mechanism(api_key_data):
    """Test login_with_api_key with AUTO mechanism (should use SCRAM if available)."""
    from truenas_api_client.auth_api_key import APIKeyAuthMech

    with Client('ws://127.0.0.1/api/current') as c:
        c.login_with_api_key('root', api_key_data['key'], APIKeyAuthMech.AUTO)
        me = c.call('auth.me')
        assert me['pw_name'] == 'root'
        assert 'API_KEY' in me['account_attributes']
        assert 'SCRAM' in me['account_attributes']


def test__login_with_api_key_scram_mechanism(api_key_data):
    """Test login_with_api_key with explicit SCRAM mechanism."""
    from truenas_api_client.auth_api_key import APIKeyAuthMech

    with Client('ws://127.0.0.1/api/current') as c:
        c.login_with_api_key('root', api_key_data['key'], APIKeyAuthMech.SCRAM)
        me = c.call('auth.me')
        assert me['pw_name'] == 'root'
        assert 'API_KEY' in me['account_attributes']
        assert 'SCRAM' in me['account_attributes']


def test__login_with_api_key_plain_mechanism(api_key_data):
    """Test login_with_api_key with explicit PLAIN mechanism (legacy)."""
    from truenas_api_client.auth_api_key import APIKeyAuthMech

    with Client('ws://127.0.0.1/api/current') as c:
        c.login_with_api_key('root', api_key_data['key'], APIKeyAuthMech.PLAIN)
        me = c.call('auth.me')
        assert me['pw_name'] == 'root'
        assert 'API_KEY' in me['account_attributes']
        assert 'SCRAM' not in me['account_attributes']  # PLAIN should not use SCRAM


def test__login_with_api_key_context_manager(api_key_data):
    """Test the example usage pattern from the user's request."""
    # This tests the pattern: with Client("ws://127.0.0.1/api/current") as c:
    #                             c.login_with_api_key(username, key)
    with Client("ws://127.0.0.1/api/current") as c:
        c.login_with_api_key('root', api_key_data['key'])
        me = c.call('auth.me')
        assert me['pw_name'] == 'root'
        assert 'API_KEY' in me['account_attributes']
        assert 'SCRAM' in me['account_attributes']


def test__login_with_api_key_file_not_found(api_key_data):
    """Test that proper error is raised when key file doesn't exist."""
    with pytest.raises(ValueError, match='Key file not found'):
        with Client('ws://127.0.0.1/api/current') as c:
            c.login_with_api_key('root', '/nonexistent/path/to/key.json')


def test__login_with_api_key_invalid_json(api_key_data):
    """Test that proper error is raised when JSON is invalid."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"invalid": json syntax}')
        f.flush()
        json_file = f.name

    try:
        with pytest.raises(ValueError, match='Key material must be either'):
            with Client('ws://127.0.0.1/api/current') as c:
                c.login_with_api_key('root', json_file)
    finally:
        os.unlink(json_file)


def test__login_with_api_key_missing_required_fields(api_key_data):
    """Test that proper error is raised when required precomputed key fields are missing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Missing server_key
        json.dump({
            'client_key': api_key_data['client_key'],
            'stored_key': api_key_data['stored_key'],
            'api_key_id': api_key_data['id']
        }, f)
        f.flush()
        json_file = f.name

    try:
        with pytest.raises(ValueError, match='Missing required field'):
            with Client('ws://127.0.0.1/api/current') as c:
                c.login_with_api_key('root', json_file)
    finally:
        os.unlink(json_file)


def test__login_with_api_key_invalid_credentials(api_key_data):
    """Test that proper error is raised with invalid API key."""
    with pytest.raises(ValueError, match='Invalid API key|Failed to authenticate'):
        with Client('ws://127.0.0.1/api/current') as c:
            c.login_with_api_key('root', '999-invalidkeydata12345')
