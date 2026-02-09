# Get and set ZFS file attributes
#
# ZFS supports various file-level attributes that are not accessible
# through normal linux filesystem APIs (for example DOS-related attributes).
#
# These utility functions allow getting and setting them
#
# NOTE: tests for parsers are in src/middlewared/middlewared/pytest/unit/utils/test_filesystem_misc.py
# Additional testing for ZFS is covered in tests/api2

import enum
import fcntl
import os
import struct

ZFS_IOC_GETATTRS = 0x80088301
ZFS_IOC_SETATTRS = 0x40088302


class ZFSAttr(enum.IntFlag):
    """
    Additional file-level attributes that are stored in upper-half of zfs
    z_pflags. See include/sys/fs/zfs.h

    NOTE: these are only available on ZFS filesystems
    """
    READONLY = 0x0000000100000000
    HIDDEN = 0x0000000200000000
    SYSTEM = 0x0000000400000000
    ARCHIVE = 0x0000000800000000
    IMMUTABLE = 0x0000001000000000
    NOUNLINK = 0x0000002000000000
    APPENDONLY = 0x0000004000000000
    NODUMP = 0x0000008000000000
    OPAQUE = 0x0000010000000000
    AV_QUARANTINED = 0x0000020000000000
    AV_MODIFIED = 0x0000040000000000
    REPARSE = 0x0000080000000000
    OFFLINE = 0x0000100000000000
    SPARSE = 0x0000200000000000


SUPPORTED_ATTRS = (
    ZFSAttr.READONLY |
    ZFSAttr.HIDDEN |
    ZFSAttr.SYSTEM |
    ZFSAttr.ARCHIVE |
    ZFSAttr.IMMUTABLE |
    ZFSAttr.NOUNLINK |
    ZFSAttr.APPENDONLY |
    ZFSAttr.OFFLINE |
    ZFSAttr.SPARSE
)


def zfs_attributes_dump(attr_mask: int) -> list[str]:
    """
    Convert bitmask of supported ZFS attributes to list
    """
    attr_mask = attr_mask & int(SUPPORTED_ATTRS)

    out = []
    for attr in ZFSAttr:
        if attr_mask & int(attr):
            if attr.name is not None:
                out.append(attr.name)

    return out


def zfs_attributes_to_dict(attr_mask: int) -> dict[str, bool]:
    """
    Convert bitmask of supported ZFS attributes to dict.
    """
    attr_mask = attr_mask & int(SUPPORTED_ATTRS)

    out = {}
    for attr in SUPPORTED_ATTRS:
        if attr.name is not None:
            out[attr.name.lower()] = bool(attr_mask & int(attr))

    return out


def dict_to_zfs_attributes_mask(attr_dict: dict[str, bool]) -> int:
    """
    Convert dictionary specification of ZFS attributes to bitmask
    for setting on file.
    """
    attr_mask = 0

    for attr, value in attr_dict.items():
        zfs_attr = ZFSAttr[attr.upper()]
        if SUPPORTED_ATTRS & zfs_attr == 0:
            raise ValueError(f'{attr}: invalid ZFS file attribute')

        if not isinstance(value, bool):
            raise TypeError(f'{attr}: value [{value}] must be boolean')

        if value is not True:
            continue

        attr_mask |= zfs_attr

    return int(attr_mask)


def zfs_attributes_to_mask(attr_list: list[str]) -> int:
    """
    Convert ZFS attribute list to bitmask for setting
    """
    attr_mask = 0

    for attr in attr_list:
        zfs_attr = ZFSAttr[attr]
        if SUPPORTED_ATTRS & zfs_attr == 0:
            raise ValueError(f'{attr}: invalid ZFS file attribute')

        attr_mask |= ZFSAttr[attr]

    return int(attr_mask)


def fget_zfs_file_attributes(fd: int) -> int:
    """
    Get bitmask of zfs atttributes on open file.

    Note: `fd` may not be an O_PATH open (READ access will be checked).
    """
    fl = struct.unpack('L', fcntl.ioctl(fd, ZFS_IOC_GETATTRS, struct.pack('L', 0)))

    if not fl:
        raise RuntimeError('Unable to retrieve zfs file attributes')

    return int(fl[0])


def fset_zfs_file_attributes(fd: int, attr_mask: int) -> int:
    """
    Set zfs attributes on open file using mask of ZFSAttrs above.
    `fd` must writeable

    NOTE: zfs attributes will be set _precisely_ as specified in the attr_mask
    If desire is to simply toggle one attribute it is simpler to use
    `set_zfs_file_attributes` below.
    """
    fcntl.ioctl(fd, ZFS_IOC_SETATTRS, struct.pack('L', attr_mask))
    return fget_zfs_file_attributes(fd)


def set_zfs_file_attributes_dict(path: str, attrs_in: dict[str, bool | None]) -> dict[str, bool]:
    """
    Set zfs file attributes on a given `path` by using the dictionary `attrs`

    Supported keys are lower-case names of SUPPORTED_ATTRS. If a supported
    key is omitted from the `attrs` payload then its current value is preserved.

    dictionary entries are of form "<attribute>" = <boolean value>

    When operation succeeds a dictionary will be returned with current values
    of attributes on the file.

    NOTE: if caller is concerned about TOCTOU issues with path lookups, then a
    procfd path ("/proc/self/fd/<fd>") with an already-open fd may be used in lieu
    of a regular filesystem path.
    """
    attrs = {key: value for key, value in attrs_in.items() if value is not None}
    open_flags = os.O_DIRECTORY if os.path.isdir(path) else os.O_RDWR

    fd = os.open(path, open_flags)

    try:
        current = zfs_attributes_to_dict(fget_zfs_file_attributes(fd))
        to_set = current | attrs
        # avoid issuing ioctl to set new attrs if we aren't changing anything
        if to_set == current:
            new_attrs = None
        else:
            new_attrs = fset_zfs_file_attributes(fd, dict_to_zfs_attributes_mask(to_set))
    finally:
        os.close(fd)

    if new_attrs is None:
        return current

    return zfs_attributes_to_dict(new_attrs)
