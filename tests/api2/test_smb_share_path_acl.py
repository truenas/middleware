import os
import pytest

from middlewared.test.integration.assets.filesystem import directory
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


@pytest.fixture(scope='module')
def fs_tree():
    with dataset('nfs4ds', data={'share_type': 'SMB'}) as ds1:
        with dataset('nfs4ds/posix') as ds2:
            # Make sure that we don't end up with collision on dataset name partial match
            with dataset(f'nfs4ds/posixcanary', {'acltype': 'POSIX', 'aclmode': 'DISCARD'}):
                mountpoint1 = os.path.join('/mnt', ds1)
                mountpoint2 = os.path.join('/mnt', ds2)
                path = os.path.join(mountpoint1, 'subdir')
                with directory(path, {'options': {'raise_chmod_error': False}}):
                    call('service.control', 'START', 'cifs', job=True)
                    try:
                        yield {
                            'mountpoint1': mountpoint1,
                            'ds1': ds1,
                            'mountpoint2': mountpoint2,
                            'ds2': ds2,
                            'subdir': path,
                        }
                    finally:
                        call('service.control', 'STOP', 'cifs', job=True)


def test__verror_share_create_acltype(fs_tree):
    with pytest.raises(Exception, match='ACL type mismatch with child mountpoint'):
        with smb_share(fs_tree['mountpoint1'], 'test_share_path'):
            pass


def test__share_create_subdir_allowed(fs_tree):
    with smb_share(fs_tree['subdir'], 'test_share_path'):
        pass


def test__share_create_child_allowed(fs_tree):
    with smb_share(fs_tree['mountpoint2'], 'test_share_path'):
        pass


def test__verror_share_update_acltype(fs_tree):
    with smb_share(fs_tree['subdir'], 'test_share_path') as share:
        with pytest.raises(Exception, match='ACL type mismatch with child mountpoint'):
            call('sharing.smb.update', share['id'], {'path': fs_tree['mountpoint1']})
