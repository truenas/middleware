import errno
import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.utils import client, call


@pytest.fixture(scope='module')
def onetime_password_user(unprivileged_user_fixture):
    yield unprivileged_user_fixture


@pytest.fixture(scope='function')
def onetime_password(onetime_password_user):
    otpw = call('auth.generate_onetime_password', {'username': onetime_password_user.username})
    yield (onetime_password_user, otpw)


def test_basic_onetime_password_auth(onetime_password):
    user, otpw = onetime_password
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': user.username,
            'password': otpw
        })
        assert resp['response_type'] == 'SUCCESS'
        assert 'OTPW' in resp['user_info']['account_attributes']


def test_onetime_password_auth_reuse_fail(onetime_password):
    user, otpw = onetime_password
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': user.username,
            'password': otpw
        })
        assert resp['response_type'] == 'SUCCESS'
        assert 'OTPW' in resp['user_info']['account_attributes']

        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': user.username,
            'password': otpw
        })
        assert resp['response_type'] == 'AUTH_ERR'


def test_onetime_password_generate_token_fail(onetime_password):
    user, otpw = onetime_password
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': user.username,
            'password': otpw
        })
        assert resp['response_type'] == 'SUCCESS'

        auth_mech_choices = c.call('auth.mechanism_choices')
        assert 'TOKEN_PLAIN' not in auth_mech_choices

        with pytest.raises(CallError) as ce:
            c.call('auth.generate_token')

        assert ce.value.errno == errno.EOPNOTSUPP


@pytest.mark.parametrize('data,revert,errmsg', (
    (
        {'password_disabled': True, 'smb': False},
        {'password_disabled': False},
        'password authentication is disabled for account.'
    ),
    (
        {'locked': True},
        {'locked': False},
        'account is locked.'
    ),
))
def test_onetime_password_validation(onetime_password_user, data, revert, errmsg):
    dbid = call('user.query', [['username', '=', onetime_password_user.username]], {'get': True})['id']
    try:
        with pytest.raises(ValidationErrors, match=errmsg):
            call('user.update', dbid, data)
            call('auth.generate_onetime_password', {'username': onetime_password_user.username})
    finally:
        call('user.update', dbid, revert)
