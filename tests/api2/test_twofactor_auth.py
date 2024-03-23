#!/usr/bin/env python3
import contextlib
import errno
import os
import sys
import pytest

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import user as user_create
from middlewared.test.integration.assets.two_factor_auth import enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
from middlewared.test.integration.assets.account import unprivileged_user
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
pytestmark = pytest.mark.accounts


@contextlib.contextmanager
def user(data: dict):
    data['group'] = call('group.query', [['gid', '=', TEST_GID]], {'get': True})['id']
    with user_create(data) as user_obj:
        yield user_obj


def test_login_without_2fa():
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
    }):
        assert call('auth.get_login_user', TEST_USERNAME, TEST_PASSWORD) is not None


@pytest.mark.parametrize("user_name,password,renew_options", [
    ('test_user1', 'test_password1', {'interval': 30, 'otp_digits': 6}),
    ('test_user2', 'test_password2', {'interval': 60, 'otp_digits': 7}),
    ('test_user3', 'test_password3', {'interval': 50, 'otp_digits': 8}),
])
def test_secret_generation_for_user(user_name, password, renew_options):
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


def test_secret_generation_for_multiple_users():
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


def test_login_without_otp_for_user_without_2fa():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
    }):
        with enabled_twofactor_auth():
            assert call('auth.get_login_user', TEST_USERNAME_2, TEST_PASSWORD_2) is not None


def test_login_with_otp_for_user_with_2fa():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
    }) as user_obj:
        with enabled_twofactor_auth():
            call('user.renew_2fa_secret', user_obj['username'], TEST_TWOFACTOR_INTERVAL)
            assert call(
                'auth.get_login_user', TEST_USERNAME_2, TEST_PASSWORD_2,
                get_2fa_totp_token(get_user_secret(user_obj['id']))
            ) is not None


def test_user_2fa_secret_renewal():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
    }) as user_obj:
        with enabled_twofactor_auth():
            call('user.renew_2fa_secret', user_obj['username'], TEST_TWOFACTOR_INTERVAL)
            assert call(
                'auth.get_login_user', TEST_USERNAME_2, TEST_PASSWORD_2,
                get_2fa_totp_token(get_user_secret(user_obj['id']))
            ) is not None
            secret = get_user_secret(user_obj['id'])

            call('user.renew_2fa_secret', user_obj['username'], TEST_TWOFACTOR_INTERVAL)
            call('user.get_instance', user_obj['id'])
            assert get_user_secret(user_obj['id'])['secret'] != secret

            assert call(
                'auth.get_login_user', TEST_USERNAME_2, TEST_PASSWORD_2,
                get_2fa_totp_token(get_user_secret(user_obj['id']))
            ) is not None


def test_restricted_user_2fa_secret_renewal():
    with unprivileged_user(
        username=TEST_USERNAME,
        group_name='TEST_2FA_GROUP',
        privilege_name='TEST_2FA_PRIVILEGE',
        allowlist=[],
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
                assert call(
                    'auth.get_login_user', acct.username, acct.password,
                    get_2fa_totp_token(get_user_secret(user_obj['id']))
                ) is not None
                secret = get_user_secret(user_obj['id'])

                c.call('user.renew_2fa_secret', acct.username, TEST_TWOFACTOR_INTERVAL)
                assert get_user_secret(user_obj['id'])['secret'] != secret

                assert call(
                    'auth.get_login_user', acct.username, acct.password,
                    get_2fa_totp_token(get_user_secret(user_obj['id']))
                ) is not None


def test_multiple_users_login_with_otp():
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
    }) as first_user:
        with enabled_twofactor_auth():
            assert call('auth.get_login_user', TEST_USERNAME, TEST_PASSWORD) is not None

            with user({
                'username': TEST_USERNAME_2,
                'password': TEST_PASSWORD_2,
                'full_name': TEST_USERNAME_2,
            }) as second_user:
                call('user.renew_2fa_secret', second_user['username'], TEST_TWOFACTOR_INTERVAL)
                assert call(
                    'auth.get_login_user', TEST_USERNAME_2, TEST_PASSWORD_2,
                    get_2fa_totp_token(get_user_secret(second_user['id']))
                ) is not None

                assert call('auth.get_login_user', TEST_USERNAME_2, TEST_PASSWORD_2) is None

                call('user.renew_2fa_secret', first_user['username'], TEST_TWOFACTOR_INTERVAL)

                assert call(
                    'auth.get_login_user', TEST_USERNAME, TEST_PASSWORD,
                    get_2fa_totp_token(get_user_secret(first_user['id']))
                ) is not None
