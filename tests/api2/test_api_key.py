import pytest

from datetime import datetime, timedelta, UTC
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client

LEGACY_ENTRY_KEY = 'rtpz6u16l42XJJGy5KMJOVfkiQH7CyitaoplXy7TqFTmY7zHqaPXuA1ob07B9bcB'
LEGACY_ENTRY_HASH = '$pbkdf2-sha256$29000$CyGktHYOwXgvBYDQOqc05g$nK1MMvVuPGHMvUENyR01qNsaZjgGmlt3k08CRuC4aTI'


@pytest.fixture(scope='function')
def sharing_admin_user(unprivileged_user_fixture):
    privilege = call('privilege.query', [['local_groups.0.group', '=', unprivileged_user_fixture.group_name]])
    assert len(privilege) > 0, 'Privilege not found'
    call('privilege.update', privilege[0]['id'], {'roles': ['SHARING_ADMIN']})

    try:
        yield unprivileged_user_fixture
    finally:
        call('privilege.update', privilege[0]['id'], {'roles': []})


def test_user_unprivileged_api_key_failure(unprivileged_user_fixture):
    """We should be able to call a method with root API key using Websocket."""
    with pytest.raises(ValidationErrors) as ve:
        with api_key(unprivileged_user_fixture.username):
            pass

    assert 'User lacks privilege role membership' in ve.value.errors[0].errmsg


def test_api_key_nonexistent_username():
    """Non-existent user should raise a validation error."""
    with pytest.raises(ValidationErrors) as ve:
        with api_key('canary'):
            pass

    assert 'User does not exist' in ve.value.errors[0].errmsg


def test_print_expired_api_key_update_failure():
    with pytest.raises(ValidationErrors) as ve:
        with api_key():
            key = call('api_key.query', [], {'get': True})
            expiry = datetime.fromtimestamp(1, UTC)
            call('api_key.update', key['id'], {'expires_at': expiry})

    assert 'Expiration date is in the past' in ve.value.errors[0].errmsg


def test_api_key_info(sharing_admin_user):
    with api_key(sharing_admin_user.username):
        key_info = call('api_key.query', [['username', '=', sharing_admin_user.username]], {'get': True})
        assert key_info['revoked'] is False
        assert key_info['expires_at'] is None
        assert key_info['local'] is True

        user = call('user.query', [['username', '=', sharing_admin_user.username]], {'get': True})
        assert user['api_keys'] == [key_info['id']]


@pytest.mark.parametrize('endpoint', ['LEGACY', 'CURRENT'])
def test_api_key_session(sharing_admin_user, endpoint):
    with api_key(sharing_admin_user.username) as key:
        with client(auth=None) as c:
            match endpoint:
                case 'LEGACY':
                    assert c.call('auth.login_with_api_key', key)
                case 'CURRENT':
                    resp = c.call('auth.login_ex', {
                        'mechanism': 'API_KEY_PLAIN',
                        'username': sharing_admin_user.username,
                        'api_key': key
                    })
                    assert resp['response_type'] == 'SUCCESS'
                case _:
                    raise ValueError(f'{endpoint}: unknown endpoint')

            session = c.call('auth.sessions', [['current', '=', True]], {'get': True})
            assert session['credentials'] == 'API_KEY'
            assert session['credentials_data']['api_key']['name'] == 'Test API Key'

            me = c.call('auth.me')
            assert me['pw_name'] == sharing_admin_user.username
            assert 'SHARING_ADMIN' in me['privilege']['roles']
            assert 'API_KEY' in me['account_attributes']

            call("auth.terminate_session", session['id'])

            with pytest.raises(Exception):
                c.call('system.info')


def test_legacy_api_key_upgrade():
    """We should automatically upgrade old hashes on successful login"""
    with api_key():
        key_id = call('api_key.query', [['username', '=', 'root']], {'get': True})['id']
        call('datastore.update', 'account.api_key', key_id, {'key': f'{key_id}-{LEGACY_ENTRY_HASH}'})
        call('etc.generate', 'pam_middleware')

        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': 'root',
               'api_key': LEGACY_ENTRY_KEY
            })
            assert resp['response_type'] == 'SUCCESS'

            # We should have replaced hash on auth
            updated = call('api_key.query', [['username', '=', 'root']], {'get': True})
            assert updated['key'] != LEGACY_ENTRY_HASH
            assert updated['key'].startswith('$pbkdf2-sha512')

        # verify we still have access
        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': 'root',
               'api_key': LEGACY_ENTRY_KEY
            })
            assert resp['response_type'] == 'SUCCESS'


def test_legacy_api_key_reject_nonroot(sharing_admin_user):
    """Old hash style should be rejected for non-root user."""
    with api_key(sharing_admin_user.username):
        key_id = call('api_key.query', [['username', '=', sharing_admin_user.username]], {'get': True})['id']
        call('datastore.update', 'account.api_key', key_id, {'key': f'{key_id}-{LEGACY_ENTRY_HASH}'})
        call('etc.generate', 'pam_middleware')

        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': sharing_admin_user.username,
               'api_key': LEGACY_ENTRY_KEY
            })
            assert resp['response_type'] == 'AUTH_ERR'


def test_api_key_expired(sharing_admin_user):
    """Expired keys should fail with expected response type"""
    with api_key(sharing_admin_user.username) as key:
        key_id = call('api_key.query', [['username', '=', sharing_admin_user.username]], {'get': True})['id']
        call('datastore.update', 'account.api_key', key_id, {'expiry': 1})

        # update our pam_tdb file with new expiration
        call('etc.generate', 'pam_middleware')

        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': sharing_admin_user.username,
               'api_key': key
            })
            assert resp['response_type'] == 'EXPIRED'


def test_key_revoked(sharing_admin_user):
    """Revoked key should raise an AUTH_ERR"""
    with api_key(sharing_admin_user.username) as key:
        key_id = call('api_key.query', [['username', '=', sharing_admin_user.username]], {'get': True})['id']
        call('datastore.update', 'account.api_key', key_id, {'expiry': -1})

        # update our pam_tdb file with revocation
        call('etc.generate', 'pam_middleware')

        revoked = call('api_key.query', [['username', '=', sharing_admin_user.username]], {'get': True})['revoked']
        assert revoked is True

        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': sharing_admin_user.username,
               'api_key': key
            })
            assert resp['response_type'] == 'AUTH_ERR'


def test_api_key_reset(sharing_admin_user):
    with api_key(sharing_admin_user.username) as key:
        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': sharing_admin_user.username,
               'api_key': key
            })
            assert resp['response_type'] == 'SUCCESS'

        key_id = call('api_key.query', [['username', '=', sharing_admin_user.username]], {'get': True})['id']
        updated = call("api_key.update", key_id, {"reset": True})

        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': sharing_admin_user.username,
               'api_key': key
            })
            assert resp['response_type'] == 'AUTH_ERR'

        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
               'mechanism': 'API_KEY_PLAIN',
               'username': sharing_admin_user.username,
               'api_key': updated['key']
            })
            assert resp['response_type'] == 'SUCCESS'
