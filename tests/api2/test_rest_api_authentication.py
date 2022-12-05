# -*- coding=utf-8 -*-
import contextlib
import io
import json

import pytest
import requests

from middlewared.test.integration.assets.account import unprivileged_user as unprivileged_user_template
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import client

import os
import sys
sys.path.append(os.getcwd())
from functions import POST, GET, DELETE, SSH_TEST
from auto_config import password, ip


@contextlib.contextmanager
def api_key_auth(allowlist):
    with api_key(allowlist) as key:
        yield dict(anonymous=True, headers={"Authorization": f"Bearer {key}"})


@contextlib.contextmanager
def login_password_auth(allowlist):
    with unprivileged_user_template(
        username="unprivileged",
        group_name="unprivileged_users",
        privilege_name="Unprivileged users",
        allowlist=allowlist,
        web_shell=False,
    ) as t:
        yield dict(auth=(t.username, t.password))


@contextlib.contextmanager
def token_auth(allowlist):
    with unprivileged_user_template(
        username="unprivileged",
        group_name="unprivileged_users",
        privilege_name="Unprivileged users",
        allowlist=allowlist,
        web_shell=False,
    ) as t:
        with client(auth=(t.username, t.password)) as c:
            token = c.call("auth.generate_token", 300, {}, True)
            yield dict(anonymous=True, headers={"Authorization": f"Token {token}"})


@pytest.fixture(params=[api_key_auth, login_password_auth, token_auth])
def auth(request):
    return request.param


def test_root_api_key_rest(auth):
    """We should be able to call a method with a root credential using REST API."""
    with auth([{"method": "*", "resource": "*"}]) as kwargs:
        results = GET('/system/info/', **kwargs)
        assert results.status_code == 200, results.text


def test_allowed_api_key_rest_plain(auth):
    """We should be able to request an endpoint with a credential that allows that request using REST API."""
    with auth([{"method": "GET", "resource": "/system/info/"}]) as kwargs:
        results = GET('/system/info/', **kwargs)
        assert results.status_code == 200, results.text


def test_allowed_api_key_rest_dynamic(auth):
    """We should be able to request a dynamic endpoint with a credential that allows that request using REST API."""
    with auth([{"method": "GET", "resource": "/user/id/{id}/"}]) as kwargs:
        results = GET('/user/id/1/', **kwargs)
        assert results.status_code == 200, results.text


def test_denied_api_key_rest(auth):
    """
    We should not be able to request an endpoint with a credential that does not allow that request using REST API.
    """
    with auth([{"method": "GET", "resource": "/system/info_/"}]) as kwargs:
        results = GET('/system/info/', **kwargs)
        assert results.status_code == 403


def test_root_api_key_upload(auth):
    """We should be able to call a method with root a credential using file upload endpoint."""
    with auth([{"method": "*", "resource": "*"}]) as kwargs:
        kwargs.pop("anonymous", None)  # This key is only used for our test requests library
        r = requests.post(
            f"http://{ip}/_upload",
            **kwargs,
            data={
                "data": json.dumps({
                    "method": "filesystem.put",
                    "params": ["/tmp/upload"],
                })
            },
            files={
                "file": io.BytesIO(b"test"),
            },
            timeout=10
        )
        r.raise_for_status()


def test_allowed_api_key_upload(auth):
    """We should be able to call a method with an API that allows that call using file upload endpoint."""
    with auth([{"method": "CALL", "resource": "filesystem.put"}]) as kwargs:
        kwargs.pop("anonymous", None)  # This key is only used for our test requests library
        r = requests.post(
            f"http://{ip}/_upload",
            **kwargs,
            data={
                "data": json.dumps({
                    "method": "filesystem.put",
                    "params": ["/tmp/upload"],
                })
            },
            files={
                "file": io.BytesIO(b"test"),
            },
            timeout=10
        )
        r.raise_for_status()


def test_denied_api_key_upload(auth):
    """
    We should not be able to call a method with a credential that does not allow that call using file upload endpoint.
    """
    with auth([{"method": "CALL", "resource": "filesystem.put_"}]) as kwargs:
        kwargs.pop("anonymous", None)  # This key is only used for our test requests library
        r = requests.post(
            f"http://{ip}/_upload",
            **kwargs,
            data={
                "data": json.dumps({
                    "method": "filesystem.put",
                    "params": ["/tmp/upload"],
                })
            },
            files={
                "file": io.BytesIO(b"test"),
            },
            timeout=10
        )
        assert r.status_code == 403
