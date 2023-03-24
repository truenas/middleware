#!/usr/bin/env python3
import contextlib
import os
import pytest
import sys
import pyotp

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.service_exception import ValidationErrors
from middlewared.test.assets.account import user
from middlewared.test.assets.two_factor_auth import enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
from middlewared.test.integration.utils import call


TEST_USERNAME = 'testuser'
TEST_USERNAME_2 = 'testuser2'
TEST_PASSWORD = 'testpassword'
TEST_PASSWORD_2 = 'testpassword2'
TEST_GID = 130


def test_login_without_2fa():
    with user({
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
        'groups': [TEST_GID],
        'full_name': TEST_USERNAME,
        'configure_twofactor_auth': True,
    }):
        assert call('auth.login', TEST_USERNAME, TEST_PASSWORD) is True


def test_secret_generation_for_user():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'groups': [TEST_GID],
        'full_name': TEST_USERNAME_2,
        'configure_twofactor_auth': True,
    }):
        assert get_user_secret(TEST_USERNAME_2, False) != []
        assert get_user_secret(TEST_USERNAME_2)['secret'] is not None


def test_login_without_otp_for_user_without_2fa():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'groups': [TEST_GID],
        'full_name': TEST_USERNAME_2,
        'configure_twofactor_auth': False,
    }):
        with enabled_twofactor_auth():
            assert call('auth.login', TEST_USERNAME_2, TEST_PASSWORD_2) is True


def test_login_with_otp_for_user_with_2fa():
    with user({
        'username': TEST_USERNAME_2,
        'password': TEST_PASSWORD_2,
        'groups': [TEST_GID],
        'full_name': TEST_USERNAME_2,
        'configure_twofactor_auth': True,
    }):
        with enabled_twofactor_auth():
            assert call(
                'auth.login', TEST_USERNAME_2, TEST_PASSWORD_2,
                get_2fa_totp_token(get_user_secret(TEST_USERNAME_2)['secret'])
            ) is True
