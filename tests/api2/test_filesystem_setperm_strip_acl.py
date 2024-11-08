import os

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


def test__strip_acl_setperm():
    """ verify ACL can be stripped on single file by explicity specifying strip """
    with dataset('stripacl_test', {'share_type': 'SMB'}) as ds:
        mp = os.path.join('/mnt', ds)

        dir_path = os.path.join(mp, 'thedir')
        assert call('filesystem.stat', mp)['acl']

        call('filesystem.mkdir', {'path': dir_path, 'options': {'raise_chmod_error': False}})
        assert call('filesystem.stat', dir_path)['acl']

        # nonrecursive
        call('filesystem.setperm', {'path': mp, 'options': {'stripacl': True}}, job=True)

        # target for setperm should not have ACL anymore
        assert not call('filesystem.stat', mp)['acl']

        # but directory should
        assert call('filesystem.stat', dir_path)['acl']

        # recursive
        call('filesystem.setperm', {'path': mp, 'options': {'stripacl': True, 'recursive': True}}, job=True)
        assert not call('filesystem.stat', dir_path)['acl']
