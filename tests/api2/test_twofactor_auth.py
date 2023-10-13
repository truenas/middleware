#!/usr/bin/env python3
import contextlib
import os
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.test.integration.assets.account import user as user_create
from middlewared.test.integration.assets.two_factor_auth import enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
from middlewared.test.integration.utils import call


TEST_USERNAME = 'test2fauser'
TEST_USERNAME_2 = 'test2fauser2'
TEST_PASSWORD = 'testpassword'
TEST_PASSWORD_2 = 'testpassword2'
TEST_GID = 544
TEST_TWOFACTOR_INTERVAL = {'interval': 60}


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


def test_secret_generation_for_user():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
    }) as user_obj:
        assert get_user_secret(user_obj['id'], False) != []
        assert get_user_secret(user_obj['id'])['secret'] is None

        call('user.renew_2fa_secret', user_obj['username'], {'interval': 70, 'otp_digits': 8})

        user_secret_obj = get_user_secret(user_obj['id'])
        assert user_secret_obj['secret'] is not None
        for k, v in (('interval', 70), ('otp_digits', 8)):
            assert user_secret_obj[k] == v


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
