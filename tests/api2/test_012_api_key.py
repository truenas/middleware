#!/usr/bin/env python3

import contextlib
import io
import json
import os
import pytest
import sys
import requests
from pytest_dependency import depends
sys.path.append(os.getcwd())
from functions import POST, GET, DELETE, SSH_TEST
from auto_config import password, user as user_, ip, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


@contextlib.contextmanager
def api_key(allowlist):
    results = POST('/api_key/', {'name': "Test API KEY", 'allowlist': allowlist})
    assert results.status_code == 200, results.text
    key = results.json()

    try:
        yield key["key"]
    finally:
        results = DELETE(f"/api_key/id/{key['id']}/")
        assert results.status_code == 200, results.text


@contextlib.contextmanager
def user():
    results = POST("/user/", {
        "username": "testuser",
        "full_name": "Test User",
        "group_create": True,
        "password": "test1234",
    })
    assert results.status_code == 200, results.text
    id = results.json()

    try:
        yield
    finally:
        results = DELETE(f"/user/id/{id}/")
        assert results.status_code == 200, results.text


def test_root_api_key_websocket(request):
    depends(request, ["ssh_password"], scope="session")
    """We should be able to call a method with root API key using Websocket."""
    with api_key([]) as key:
        with user():
            cmd = f"sudo -u testuser midclt -u ws://{ip}/websocket --api-key {key} call system.info"
            results = SSH_TEST(cmd, user_, password, ip)
        assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'
        assert 'uptime' in str(results['output'])


def test_allowed_api_key_websocket(request):
    depends(request, ["ssh_password"], scope="session")
    """We should be able to call a method with API key that allows that call using Websocket."""
    with api_key([{"method": "CALL", "resource": "system.info"}]) as key:
        with user():
            cmd = f"sudo -u testuser midclt -u ws://{ip}/websocket --api-key {key} call system.info"
            results = SSH_TEST(cmd, user_, password, ip)
        assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'
        assert 'uptime' in str(results['output'])


def test_denied_api_key_websocket(request):
    depends(request, ["ssh_password"], scope="session")
    """We should not be able to call a method with API key that does not allow that call using Websocket."""
    with api_key([{"method": "CALL", "resource": "system.info_"}]) as key:
        with user():
            cmd = f"sudo -u testuser midclt -u ws://{ip}/websocket --api-key {key} call system.info"
            results = SSH_TEST(cmd, user_, password, ip)
        assert results['result'] is False


def test_root_api_key_rest():
    """We should be able to call a method with root API key using REST API."""
    with api_key([]) as key:
        results = GET('/system/info/', anonymous=True, headers={"Authorization": f"Bearer {key}"})
        assert results.status_code == 200, results.text


def test_allowed_api_key_rest_plain():
    """We should be able to request an endpoint with API key that allows that request using REST API."""
    with api_key([{"method": "GET", "resource": "/system/info/"}]) as key:
        results = GET('/system/info/', anonymous=True, headers={"Authorization": f"Bearer {key}"})
        assert results.status_code == 200, results.text


def test_allowed_api_key_rest_dynamic():
    """We should be able to request a dynamic endpoint with API key that allows that request using REST API."""
    with api_key([{"method": "GET", "resource": "/user/id/{id}/"}]) as key:
        results = GET('/user/id/1/', anonymous=True, headers={"Authorization": f"Bearer {key}"})
        assert results.status_code == 200, results.text


def test_denied_api_key_rest():
    """We should not be able to request an endpoint with API key that does not allow that request using REST API."""
    with api_key([{"method": "GET", "resource": "/system/info_/"}]) as key:
        results = GET('/system/info/', anonymous=True, headers={"Authorization": f"Bearer {key}"})
        assert results.status_code == 403


def test_root_api_key_upload():
    """We should be able to call a method with root API key using file upload endpoint."""
    with api_key([]) as key:
        r = requests.post(
            f"http://{ip}/_upload",
            headers={"Authorization": f"Bearer {key}"},
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


def test_allowed_api_key_upload():
    """We should be able to call a method with an API that allows that call using file upload endpoint."""
    with api_key([{"method": "CALL", "resource": "filesystem.put"}]) as key:
        r = requests.post(
            f"http://{ip}/_upload",
            headers={"Authorization": f"Bearer {key}"},
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


def test_denied_api_key_upload():
    """We should not be able to call a method with API key that does not allow that call using file upload endpoint."""
    with api_key([{"method": "CALL", "resource": "filesystem.put_"}]) as key:
        r = requests.post(
            f"http://{ip}/_upload",
            headers={"Authorization": f"Bearer {key}"},
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
