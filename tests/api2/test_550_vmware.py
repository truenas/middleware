import sys
import os

import pytest

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


@pytest.mark.skipif(not vmw_credentials, reason='Test only valid with VM credentials')
def test_02_create_vmware():
    payload = {
        'hostname': VMWARE_HOST,
        'username': VMWARE_USERNAME,
        'password': VMWARE_PASSWORD
    }
    results = POST('/vmware/get_datastores/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text

@pytest.mark.skipif(not vmw_credentials, reason='Test only valid with VM credentials')
def test_03_verify_vmware_get_datastore_do_not_leak_password(request):
    cmd = f"grep -R \"{os.environ['VMWARE_PASSWORD']}\" " \
        "/var/log/middlewared.log"
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is False, str(results['output'])
