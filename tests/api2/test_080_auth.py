#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, SSH_TEST
from auto_config import password, user, ip, dev_test

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

invalid_users = [
    {'username': 'root', 'password': '123'},
    {'username': 'test', 'password': 'test'},
]


def test_01_check_valid_root_user_authentication():
    payload = {"username": user,
               "password": password}
    results = POST("/auth/check_user/", payload)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_02_verify_auth_does_not_leak_password_into_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = f"""grep -R "{password}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


@pytest.mark.parametrize('data_user', invalid_users)
def test_03_auth_check_invalid_user(data_user):
    results = POST('/auth/check_user/', data_user)
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@pytest.mark.parametrize('data_random', [None, 1000, 2000, 3000, 4000, 5000])
def test_04_auth_generate_token(data_random):
    results = POST('/auth/generate_token/', {'ttl': data_random})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str) is True, results.text
