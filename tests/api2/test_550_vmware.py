import pytest

from middlewared.test.integration.utils import call, ssh

try:
    from config import VMWARE_HOST, VMWARE_USERNAME, VMWARE_PASSWORD
    vmw_credentials = True
except ImportError:
    vmw_credentials = False


@pytest.mark.skipif(not vmw_credentials, reason='VMWARE credentials are missing')
def test_create_vmware():

    call('vmware.query')

    payload = {
        'hostname': VMWARE_HOST,
        'username': VMWARE_USERNAME,
        'password': VMWARE_PASSWORD
    }
    results = call('vmware.get_datastores', payload)

@pytest.mark.skipif(not vmw_credentials, reason='VMWARE credentials are missing')
def test_verify_vmware_get_datastore_do_not_leak_password(request):
    cmd = f'grep -R "{VMWARE_PASSWORD}" ' \
        '/var/log/middlewared.log'
    results = ssh(cmd, complete_response=True)
    assert results['result'] is False
