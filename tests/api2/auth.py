#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import password, user

invalid_users = [
    {'username': 'root', 'password': '123'},
    {'username': 'test', 'password': 'test'},
]


def test_01_check_valid_root_user_authentification():
    payload = {"username": user,
               "password": password}
    results = POST("/auth/check_user/", payload)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@pytest.mark.parametrize('data_user', invalid_users)
def test_02_auth_check_invalid_user(data_user):
    results = POST('/auth/check_user/', data_user)
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@pytest.mark.parametrize('data_random', [None, 1000, 2000, 3000, 4000, 5000])
def test_03_auth_generate_token(data_random):
    results = POST('/auth/generate_token/', {'ttl': data_random})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str) is True, results.text
