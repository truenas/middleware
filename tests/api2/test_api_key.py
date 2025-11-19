import errno
import pytest

from datetime import datetime, UTC
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client
from middlewared.test.integration.utils.alert import process_alerts
from time import sleep

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


def check_revoked_alert():
    process_alerts()

    for a in call('alert.list'):
        if a['klass'] == 'ApiKeyRevoked':
            return a

    return None


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

        assert check_revoked_alert() is not None
        call('datastore.update', 'account.api_key', key_id, {'expiry': 0})
        sleep(1)
        alert = check_revoked_alert()
        assert alert is None, str(alert)


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


def test_api_key_crud_restricted_admin_own_keys(sharing_admin_user):
    with client(auth=(sharing_admin_user.username, sharing_admin_user.password)) as c:
        key_info = c.call('api_key.create', {
            'username': sharing_admin_user.username,
            'name': 'test_restricted_admin_key',
        })

        try:
            updated = c.call('api_key.update', key_info['id'], {
                'name': 'test_restricted_admin_key_new'
            })
            assert 'key' not in updated
            updated = c.call('api_key.update', key_info['id'], {'reset': True})
            assert updated['key'] != '********'
        finally:
            c.call('api_key.delete', key_info['id'])


def test_api_key_restrict_admin_other_keys_fail(sharing_admin_user):
    with client(auth=(sharing_admin_user.username, sharing_admin_user.password)) as c:
        with pytest.raises(CallError) as ce:
            c.call('api_key.create', {
                'username': 'root',
                'name': 'test_restricted_admin_key',
            })

        assert ce.value.errno == errno.EACCES


def test_api_key_revoke_insecure_transport(sharing_admin_user):
    with api_key(sharing_admin_user.username) as key:
        with client(auth=None, ssl=False) as c:
            resp = c.call('auth.login_ex', {
                'mechanism': 'API_KEY_PLAIN',
                'username': sharing_admin_user.username,
                'api_key': key
            })
            assert resp['response_type'] == 'EXPIRED'

        # When the key is revoked due to use over insecure transport, it should
        # automatically generate an alert that the key has been revoked.
        alert = check_revoked_alert()
        assert alert
        assert alert['formatted'].startswith(
            'Test API Key: API key has been revoked and must either be renewed or deleted. '
            'Revoke reason: Attempt to use over an insecure transport.'
        )
