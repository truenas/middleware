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


@pytest.fixture(scope='module')
def mount_share(setup_smb_tests):
    with smb_mount(setup_smb_tests['share']['name'], 'smbuser', 'Abcd1234$') as mp:
        yield setup_smb_tests | {'mountpoint': mp} 


def test_smb_mount(request, mount_share):
    assert call('filesystem.statfs', mount_share['mountpoint'])['fstype'] == 'cifs'


def test_acl_share_root(request, mount_share):
    local_acl = call('filesystem.getacl', os.path.join('/mnt', mount_share['dataset']))
    local_acl.pop('path')
    smb_acl = call('filesystem.getacl', mount_share['mountpoint'])
    smb_acl.pop('path')

    assert local_acl == smb_acl
