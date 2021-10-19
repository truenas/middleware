#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST
from auto_config import ip, user, password, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

try:
    Reason = 'VMWARE credentials credential is missing'
    from config import VMWARE_HOST, VMWARE_USERNAME, VMWARE_PASSWORD
    vmw_credentials = True
except ImportError:
    vmw_credentials = False


def test_01_get_vmware_query():
    results = GET('/vmware/')
    assert results.status_code == 200
    assert isinstance(results.json(), list) is True


if vmw_credentials:
    def test_02_create_vmware():
        payload = {
            'hostname': VMWARE_HOST,
            'username': VMWARE_USERNAME,
            'password': VMWARE_PASSWORD
        }
        results = POST('/vmware/get_datastores/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text

    def test_03_verify_vmware_get_datastore_do_not_leak_password(request):
        depends(request, ["ssh_password"], scope="session")
        cmd = f"grep -R \"{os.environ['VMWARE_PASSWORD']}\" " \
            "/var/log/middlewared.log"
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is False, str(results['output'])
