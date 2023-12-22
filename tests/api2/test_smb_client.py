import os
import pytest

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share, smb_mount 
from middlewared.test.integration.utils import call, client


@pytest.fixture(scope='module')
def setup_smb_tests(request):
    with dataset('smb-cifs', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': 'smbuser',
            'full_name': 'smbuser',
            'group_create': True,
            'password': 'Abcd1234$' 
        }) as u:
            with smb_share(os.path.join('/mnt', ds), 'client_share') as s:
                try:
                    call('service.start', 'cifs')
                    yield {'dataset': ds, 'share': s, 'user': u}
                finally:
                    call('service.stop', 'cifs')


@pytest.fixture(scope='function')
def mount_share(setup_smb_tests):
    with smb_mount(share_data['share']['name'], 'smbuser', 'Abcd1234$') as mp:
        yield setup_smb_tests | {'mountpoint': mp} 


def test_test_smb_mount(request, mount_share):
    assert call('filesystem.statfs', mount_share['mountpoint'])['fstype'] == 'cifs'
