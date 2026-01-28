import contextlib
from datetime import datetime, timezone
import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import user as user_create
from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.assets.two_factor_auth import (
    enabled_twofactor_auth, get_user_secret, get_user_secret_sid, get_2fa_totp_token,
)
from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client


TEST_USERNAME = 'test2fauser'
TEST_USERNAME_2 = 'test2fauser2'
TEST_PASSWORD = 'testpassword'
TEST_PASSWORD_2 = 'testpassword2'
TEST_GID = 544
TEST_TWOFACTOR_INTERVAL = {'interval': 60}
USERS_2FA_CONF = {
    TEST_USERNAME: {'interval': 30, 'otp_digits': 6},
    TEST_USERNAME_2: {'interval': 40, 'otp_digits': 7}
}


@contextlib.contextmanager
def user(data: dict):
    data['group'] = call('group.query', [['gid', '=', TEST_GID]], {'get': True})['id']
    with user_create(data) as user_obj:
        yield user_obj


@pytest.fixture(scope='function')
def clear_ratelimit():
    call('rate.limit.cache_clear')


@pytest.fixture(scope='module', autouse=True)
def ensure_small_time_difference():
    nas_time = call('system.info')['datetime']
    local_time = datetime.now(timezone.utc)
    if abs((nas_time - local_time).total_seconds()) > 5:
        raise Exception(f'Time difference between NAS ({nas_time!r}) and test client ({local_time}) is too large')


@pytest.fixture(scope='function')
def enterprise_ad():
    with product_type():
        with directoryservice('ACTIVEDIRECTORY') as ad:
            call("system.general.update", {"ds_auth": True})
            try:
                yield ad
            finally:
                call("system.general.update", {"ds_auth": False})


def do_login(username, password, otp=None, expected=True):
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': username,
            'password': password,
        })
        if not otp and expected:
            assert resp['response_type'] == 'SUCCESS'
        elif not otp and not expected:
            assert resp['response_type'] in ('AUTH_ERR', 'OTP_REQUIRED')
        else:
            assert resp['response_type'] == 'OTP_REQUIRED'

        if not otp:
            return

        resp = c.call('auth.login_ex_continue', {
            'mechanism': 'OTP_TOKEN',
            'otp_token': otp
        })
        if expected:
            assert resp['response_type'] == 'SUCCESS'
        else:
            assert resp['response_type'] == 'AUTH_ERR'


def test_login_without_2fa(clear_ratelimit):
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
    }):
        do_login(TEST_USERNAME, TEST_PASSWORD)


@pytest.mark.parametrize("user_name,password,renew_options", [
    ('test_user1', 'test_password1', {'interval': 30, 'otp_digits': 6}),
    ('test_user2', 'test_password2', {'interval': 60, 'otp_digits': 7}),
    ('test_user3', 'test_password3', {'interval': 50, 'otp_digits': 8}),
])
def test_secret_generation_for_user(user_name, password, renew_options, clear_ratelimit):
    with user({
        'username': user_name,
        'password': password,
        'full_name': user_name,
    }) as user_obj:
        assert get_user_secret(user_obj['id'], False) != []
        assert get_user_secret(user_obj['id'])['secret'] is None

        call('user.renew_2fa_secret', user_obj['username'], renew_options)

        user_secret_obj = get_user_secret(user_obj['id'])
        assert user_secret_obj['secret'] is not None
        for k in ('interval', 'otp_digits'):
            assert user_secret_obj[k] == renew_options[k]


def test_secret_generation_for_multiple_users(clear_ratelimit):
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
    }) as first_user:
        call('user.renew_2fa_secret', first_user['username'], USERS_2FA_CONF[first_user['username']])
        with user({
            'username': TEST_USERNAME_2,
            'password': TEST_PASSWORD_2,
            'full_name': TEST_USERNAME_2,
        }) as second_user:
            call('user.renew_2fa_secret', second_user['username'], USERS_2FA_CONF[second_user['username']])
            for user_obj in (first_user, second_user):
                user_secret_obj = get_user_secret(user_obj['id'])
                assert user_secret_obj['secret'] is not None
                for k in ('interval', 'otp_digits'):
                    assert user_secret_obj[k] == USERS_2FA_CONF[user_obj['username']][k]


def test_login_without_otp_for_user_without_2fa(clear_ratelimit):
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
    }):
        with enabled_twofactor_auth():
            do_login(TEST_USERNAME_2, TEST_PASSWORD_2)


def test_login_with_otp_for_user_with_2fa(clear_ratelimit):
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
    }) as user_obj:
        with enabled_twofactor_auth():
            call('user.renew_2fa_secret', user_obj['username'], TEST_TWOFACTOR_INTERVAL)
            do_login(TEST_USERNAME_2, TEST_PASSWORD_2, get_2fa_totp_token(get_user_secret(user_obj['id'])))


def test_user_2fa_secret_renewal(clear_ratelimit):
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
    }) as user_obj:
        with enabled_twofactor_auth():
            call('user.renew_2fa_secret', user_obj['username'], TEST_TWOFACTOR_INTERVAL)
            do_login(TEST_USERNAME_2, TEST_PASSWORD_2, get_2fa_totp_token(get_user_secret(user_obj['id'])))
            secret = get_user_secret(user_obj['id'])

            call('user.renew_2fa_secret', user_obj['username'], TEST_TWOFACTOR_INTERVAL)
            call('user.get_instance', user_obj['id'])
            assert get_user_secret(user_obj['id'])['secret'] != secret
            do_login(TEST_USERNAME_2, TEST_PASSWORD_2, get_2fa_totp_token(get_user_secret(user_obj['id'])))


def test_restricted_user_2fa_secret_renewal(clear_ratelimit):
    with unprivileged_user(
        username=TEST_USERNAME,
        group_name='TEST_2FA_GROUP',
        privilege_name='TEST_2FA_PRIVILEGE',
        web_shell=False,
        roles=['READONLY_ADMIN']
    ) as acct:
        with enabled_twofactor_auth():
            with client(auth=(acct.username, acct.password)) as c:
                with pytest.raises(CallError) as ve:
                    # Trying to renew another user's 2fa token should fail
                    c.call('user.renew_2fa_secret', "root", TEST_TWOFACTOR_INTERVAL)

                assert ve.value.errno == errno.EPERM

                c.call('user.renew_2fa_secret', acct.username, TEST_TWOFACTOR_INTERVAL)
                user_obj = call('user.query', [['username', '=', acct.username]], {'get': True})
                do_login(acct.username, acct.password, get_2fa_totp_token(get_user_secret(user_obj['id'])))

                secret = get_user_secret(user_obj['id'])

                c.call('user.renew_2fa_secret', acct.username, TEST_TWOFACTOR_INTERVAL)
                assert get_user_secret(user_obj['id'])['secret'] != secret

                do_login(acct.username, acct.password, get_2fa_totp_token(get_user_secret(user_obj['id'])))


def test_multiple_users_login_with_otp(clear_ratelimit):
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
    }) as first_user:
        with enabled_twofactor_auth():
            do_login(TEST_USERNAME, TEST_PASSWORD)

            with user({
                'username': TEST_USERNAME_2,
                'password': TEST_PASSWORD_2,
                'full_name': TEST_USERNAME_2,
            }) as second_user:
                call('user.renew_2fa_secret', second_user['username'], TEST_TWOFACTOR_INTERVAL)
                otp_token = get_2fa_totp_token(get_user_secret(second_user['id']))
                do_login(TEST_USERNAME_2, TEST_PASSWORD_2, otp_token)

                # verify we can't replay same token
                do_login(TEST_USERNAME_2, TEST_PASSWORD_2, otp_token, expected=False)

                # Verify 2FA still required
                do_login(TEST_USERNAME_2, TEST_PASSWORD_2, expected=False)

                call('user.renew_2fa_secret', first_user['username'], TEST_TWOFACTOR_INTERVAL)
                do_login(TEST_USERNAME, TEST_PASSWORD, get_2fa_totp_token(get_user_secret(first_user['id'])))


def test_login_with_otp_failure(clear_ratelimit):
    """ simulate continually fat-fingering OTP token until eventual failure """
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
    }) as u:
        with enabled_twofactor_auth():
            call('user.renew_2fa_secret', u['username'], TEST_TWOFACTOR_INTERVAL)

            with client(auth=None) as c:
                resp = c.call('auth.login_ex', {
                    'mechanism': 'PASSWORD_PLAIN',
                    'username': TEST_USERNAME,
                    'password': TEST_PASSWORD,
                })
                assert resp['response_type'] == 'OTP_REQUIRED'

                resp = c.call('auth.login_ex_continue', {
                    'mechanism': 'OTP_TOKEN',
                    'otp_token': 'canary'
                })
                assert resp['response_type'] == 'AUTH_ERR'


def test_login_with_otp_switch_account(clear_ratelimit):
    """ Validate we can abandon a login attempt with 2FA """
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
    }) as u:
        with user({
            'username': TEST_USERNAME_2,
            'password': TEST_PASSWORD_2,
            'full_name': TEST_USERNAME_2,
        }):
            with enabled_twofactor_auth():
                call('user.renew_2fa_secret', u['username'], TEST_TWOFACTOR_INTERVAL)

                with client(auth=None) as c:
                    resp = c.call('auth.login_ex', {
                        'mechanism': 'PASSWORD_PLAIN',
                        'username': TEST_USERNAME,
                        'password': TEST_PASSWORD,
                    })
                    assert resp['response_type'] == 'OTP_REQUIRED'

                    resp = c.call('auth.login_ex', {
                        'mechanism': 'PASSWORD_PLAIN',
                        'username': TEST_USERNAME_2,
                        'password': TEST_PASSWORD_2,
                    })
                    assert resp['response_type'] == 'SUCCESS'


def test_login_with_ad_otp(clear_ratelimit, enterprise_ad):
    """ Validate AD account can use 2FA """
    with enabled_twofactor_auth():
        username = enterprise_ad['account'].user_obj['pw_name']
        user_obj = call('user.query', [['username', '=', username]], {'get': True})
        assert user_obj['twofactor_auth_configured'] is False

        call('user.renew_2fa_secret', user_obj['username'], TEST_TWOFACTOR_INTERVAL)
        user_obj = call('user.query', [['username', '=', username]], {'get': True})
        assert user_obj['twofactor_auth_configured'] is True

        user_secret_obj = get_user_secret_sid(user_obj['sid'], True)
        assert user_secret_obj['secret'] is not None

        do_login(user_obj['username'], enterprise_ad['account'].password, get_2fa_totp_token(user_secret_obj))
