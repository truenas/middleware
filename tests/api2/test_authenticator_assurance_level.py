import errno
import pytest

from contextlib import contextmanager
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.two_factor_auth import enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import client, call, password


@contextmanager
def authenticator_assurance_level(level):
    """ temporarily increase level """
    with client() as c:
        c.call('auth.set_authenticator_assurance_level', level)
        try:
            yield
        finally:
            c.call('auth.set_authenticator_assurance_level', 'LEVEL_1')


@pytest.fixture(scope='function')
def sharing_admin_user(unprivileged_user_fixture):
    privilege = call('privilege.query', [['local_groups.0.group', '=', unprivileged_user_fixture.group_name]])
    assert len(privilege) > 0, 'Privilege not found'
    call('privilege.update', privilege[0]['id'], {'roles': ['SHARING_ADMIN']})

    try:
        yield unprivileged_user_fixture
    finally:
        call('privilege.update', privilege[0]['id'], {'roles': []})


@pytest.mark.parametrize('level,expected', [
    ('LEVEL_1', ['API_KEY_PLAIN', 'TOKEN_PLAIN', 'PASSWORD_PLAIN', 'SCRAM']),
    ('LEVEL_2', ['PASSWORD_PLAIN', 'SCRAM']),
])
def test_mechanism_choices(level, expected):
    with authenticator_assurance_level(level):
        assert call('auth.mechanism_choices') == expected


def test_level2_api_key_plain():
    """ API_KEY_PLAIN lacks replay resistance
    and so authentication attempts must fail with AUTH_ERR
    """
    with authenticator_assurance_level('LEVEL_2'):
        with api_key() as key:
            with client(auth=None) as c:
                with pytest.raises(CallError) as ce:
                    call('auth.login_ex', {
                        'mechanism': 'API_KEY_PLAIN',
                        'username': 'root',
                        'api_key': key
                    })

                assert ce.value.errno == errno.EOPNOTSUPP


def test_level2_password_plain_no_twofactor():
    """ PASSWORD_PLAIN lacks replay resistance
    and so authentication attempts must fail with AUTH_ERR
    """
    with authenticator_assurance_level('LEVEL_2'):
        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
                'mechanism': 'PASSWORD_PLAIN',
                'username': 'root',
                'password': password()

            })

            assert resp['response_type'] == 'AUTH_ERR'


def test_level2_password_with_otp(sharing_admin_user):
    """ PASSWORD_PLAIN with 2FA is sufficient to authenticate """
    user_obj_id = call('user.query', [['username', '=', sharing_admin_user.username]], {'get': True})['id']

    with enabled_twofactor_auth():
        call('user.renew_2fa_secret', sharing_admin_user.username, {'interval': 60})
        secret = get_user_secret(user_obj_id)

        with authenticator_assurance_level('LEVEL_2'):
            with client(auth=None) as c:
                resp = c.call('auth.login_ex', {
                    'mechanism': 'PASSWORD_PLAIN',
                    'username': sharing_admin_user.username,
                    'password': sharing_admin_user.password
                })
                assert resp['response_type'] == 'OTP_REQUIRED'
                assert resp['username'] == sharing_admin_user.username

                resp = c.call('auth.login_ex', {
                    'mechanism': 'OTP_TOKEN',
                    'otp_token': get_2fa_totp_token(secret)
                })

                assert resp['response_type'] == 'SUCCESS'
                assert resp['authenticator'] == 'LEVEL_2'

                # Generating a token should fail
                with pytest.raises(CallError) as ce:
                    c.call('auth.generate_token')

                assert ce.value.errno == errno.EOPNOTSUPP


def test_level2_onetime_password(sharing_admin_user):
    onetime_password = call('auth.generate_onetime_password', {'username': sharing_admin_user.username})

    with authenticator_assurance_level('LEVEL_2'):
        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
                'mechanism': 'PASSWORD_PLAIN',
                'username': sharing_admin_user.username,
                'password': onetime_password
            })
            assert resp['response_type'] == 'SUCCESS'
            assert resp['authenticator'] == 'LEVEL_2'

            me = c.call('auth.me')
            assert me['pw_name'] == sharing_admin_user.username
            assert 'SHARING_ADMIN' in me['privilege']['roles']
            assert 'OTPW' in me['account_attributes']

            # attempt to reuse the onetime password should fail with AUTH_ERR
            # because we don't want to leak info about onetime password status.
            resp = c.call('auth.login_ex', {
                'mechanism': 'PASSWORD_PLAIN',
                'username': sharing_admin_user.username,
                'password': onetime_password
            })

            assert resp['response_type'] == 'AUTH_ERR'
