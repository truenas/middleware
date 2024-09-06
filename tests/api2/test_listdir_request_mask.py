import enum
import pytest

from middlewared.test.integration.utils import call


class DirectoryRequestMask(enum.IntFlag):
    ACL = enum.auto()
    CTLDIR = enum.auto()
    REALPATH = enum.auto()
    XATTRS = enum.auto()
    ZFS_ATTRS = enum.auto()


@pytest.mark.parametrize('select_key,request_mask', [
    ('realpath', DirectoryRequestMask.REALPATH.value),
    ('acl', DirectoryRequestMask.ACL.value),
    ('zfs_attrs', DirectoryRequestMask.ZFS_ATTRS.value),
    ('is_ctldir', DirectoryRequestMask.CTLDIR.value),
    ('xattrs', DirectoryRequestMask.XATTRS.value),
    (['xattrs', 'user_xattrs'], DirectoryRequestMask.XATTRS.value),
    ([], None),
    ('name', 0)
])
def test__select_to_request_mask(select_key, request_mask):
    if select_key == []:
        val = call('filesystem.listdir_request_mask', [])
        assert val is None
    else:
        val = call('filesystem.listdir_request_mask', [select_key])
        assert val == request_mask
