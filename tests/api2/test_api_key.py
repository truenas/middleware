#!/usr/bin/env python3

import contextlib
import os
import pytest
import sys
from pytest_dependency import depends
sys.path.append(os.getcwd())
from functions import POST, GET, DELETE, SSH_TEST
from auto_config import password, user as user_, ip, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for development testing')

from middlewared.test.integration.assets.api_key import api_key


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
    with api_key([{"method": "*", "resource": "*"}]) as key:
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
