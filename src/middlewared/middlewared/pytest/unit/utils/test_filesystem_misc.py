import pytest

from middlewared.utils.filesystem import acl
from middlewared.utils.filesystem import attrs


@pytest.mark.parametrize('xattr_list,expected', [
    ([acl.ACLXattr.POSIX_ACCESS.value], True),
    ([acl.ACLXattr.POSIX_DEFAULT.value], True),
    ([acl.ACLXattr.ZFS_NATIVE.value], True),
    ([], False),
])
def test__acl_is_present(xattr_list, expected):
    assert acl.acl_is_present(xattr_list) is expected


def test__zfs_attrs_enum():
    for attr in attrs.SUPPORTED_ATTRS:
        assert attr in attrs.ZFSAttr


@pytest.mark.parametrize('attr', attrs.SUPPORTED_ATTRS)
def test__zfs_attr_mask_conversion(attr):
    # Check that it gets converted to list properly:
    assert attrs.zfs_attributes_dump(attr) == [attr.name.upper()]

    attr_dict = {a.name.lower(): False for a in attrs.SUPPORTED_ATTRS}
    assert attrs.zfs_attributes_to_dict(attr) == attr_dict | {attr.name.lower(): True}


@pytest.mark.parametrize('attr', attrs.SUPPORTED_ATTRS)
def test__dict_to_attr_mask_conversion_single(attr):
    payload = {attr.name.lower(): True}
    assert attrs.dict_to_zfs_attributes_mask(payload) == attr


def test__dict_to_attr_mask_conversion_multi():
    payload = {attr.name.lower(): True for attr in attrs.SUPPORTED_ATTRS}
    assert attrs.dict_to_zfs_attributes_mask(payload) == attrs.SUPPORTED_ATTRS


@pytest.mark.parametrize('attr', attrs.SUPPORTED_ATTRS)
def test__list_to_attr_mask_conversion_single(attr):
    payload = [attr.name]
    assert attrs.zfs_attributes_to_mask(payload) == attr


def test__list_to_attr_mask_conversion_multi():
    payload = [attr.name for attr in attrs.SUPPORTED_ATTRS]
    assert attrs.zfs_attributes_to_mask(payload) == attrs.SUPPORTED_ATTRS
