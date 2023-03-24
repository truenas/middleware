#!/usr/bin/env python3
import contextlib
import os
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.client import Client
from middlewared.test.integration.assets.account import user as user_create
from middlewared.test.integration.assets.two_factor_auth import enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
from middlewared.test.integration.utils import call


TEST_USERNAME = 'testuser'
TEST_USERNAME_2 = 'testuser2'
TEST_PASSWORD = 'testpassword'
TEST_PASSWORD_2 = 'testpassword2'
TEST_GID = 544


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
        'configure_twofactor_auth': True,
    }):
        assert call('auth.login', TEST_USERNAME, TEST_PASSWORD) is True


def test_secret_generation_for_user():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
        'configure_twofactor_auth': True,
    }) as user_obj:
        assert get_user_secret(user_obj['id'], False) != []
        assert get_user_secret(user_obj['id'])['secret'] is not None


def test_login_without_otp_for_user_without_2fa():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
        'configure_twofactor_auth': False,
    }):
        with enabled_twofactor_auth():
            assert call('auth.login', TEST_USERNAME_2, TEST_PASSWORD_2) is True


def test_login_with_otp_for_user_with_2fa():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
        'configure_twofactor_auth': True,
    }) as user_obj:
        with enabled_twofactor_auth():
            assert call(
                'auth.login', TEST_USERNAME_2, TEST_PASSWORD_2,
                get_2fa_totp_token(get_user_secret(user_obj['id'])['secret'])
            ) is True


def test_user_2fa_secret_renewal():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'full_name': TEST_USERNAME_2,
        'configure_twofactor_auth': True,
    }) as user_obj:
        with enabled_twofactor_auth():
            assert call(
                'auth.login', TEST_USERNAME_2, TEST_PASSWORD_2,
                get_2fa_totp_token(get_user_secret(user_obj['id'])['secret'])
            ) is True
            secret = get_user_secret(user_obj['id'])['secret']

            call('user.update', user_obj['id'], {'renew_twofactor_secret': True})
            call('user.get_instance', user_obj['id'])
            assert get_user_secret(user_obj['id'])['secret'] != secret

            assert call(
                'auth.login', TEST_USERNAME_2, TEST_PASSWORD_2,
                get_2fa_totp_token(get_user_secret(user_obj['id'])['secret'])
            ) is True


def test_multiple_users_login_with_otp():
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'full_name': TEST_USERNAME,
        'configure_twofactor_auth': False,
    }) as first_user:
        with enabled_twofactor_auth():
            assert call('auth.login', TEST_USERNAME, TEST_PASSWORD) is True

            with user({
                'username': TEST_USERNAME_2,
                'password': TEST_PASSWORD_2,
                'full_name': TEST_USERNAME_2,
                'configure_twofactor_auth': True,
            }) as second_user:
                assert call(
                    'auth.login', TEST_USERNAME_2, TEST_PASSWORD_2,
                    get_2fa_totp_token(get_user_secret(second_user['id'])['secret'])
                ) is True

                assert call('auth.login', TEST_USERNAME_2, TEST_PASSWORD_2) is False

                call('user.update', first_user['id'], {'renew_twofactor_secret': True})

                assert call(
                    'auth.login', TEST_USERNAME, TEST_PASSWORD,
                    get_2fa_totp_token(get_user_secret(first_user['id'])['secret'])
                ) is True
