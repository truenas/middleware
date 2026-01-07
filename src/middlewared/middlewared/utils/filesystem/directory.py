# This provides a middleware backend oriented directory generator that
# is primarily consumed by filesystem.listdir, but may be used in other
# places. It is primarily a thin wrapper around os.scandir, but also
# provides statx output and other optional file information in the
# returned dictionaries.
#
# NOTE: tests for these utils are in src/middlewared/middlewared/pytest/unit/utils/test_directory.py


import enum
import errno
import os
import pathlib

from collections import namedtuple
from truenas_os import AT_EMPTY_PATH, statx, StatxResult
from .acl import acl_is_present
from .attrs import fget_zfs_file_attributes, zfs_attributes_dump
from .constants import FileType
from .stat_x import statx_entry_impl, STATX_DEFAULT_MASK
from .utils import path_in_ctldir


class DirectoryRequestMask(enum.IntFlag):
    """
    Allow users to specify what information they want with the returned
    directory object. Removing unnecessary information may be useful to
    improve performance of the DirectoryIterator.

    ACL - include boolean whether ACL is present (requires listxattr call)

    CTLDIR - include boolean whether path is in ZFS ctldir (requires multiple
        stat() calls per file

    REALPATH - include output of `realpath` call

    XATTR - list of extended attributes (requires listxattr call)

    ZFS_ATTRS - include ZFS attributes (requires fcntl call per file)

    NOTE: this changes to this should also be reflected in API test
    `test_listdir_request_mask.py`
    """
    ACL = enum.auto()
    CTLDIR = enum.auto()
    REALPATH = enum.auto()
    XATTRS = enum.auto()
    ZFS_ATTRS = enum.auto()


ALL_ATTRS = (
    DirectoryRequestMask.ACL |
    DirectoryRequestMask.CTLDIR |
    DirectoryRequestMask.REALPATH |
    DirectoryRequestMask.XATTRS |
    DirectoryRequestMask.ZFS_ATTRS
)

dirent_struct = namedtuple('struct_dirent', [
    'name', 'path', 'realpath', 'stat', 'etype', 'acl', 'xattrs', 'zfs_attrs', 'is_in_ctldir'
])


class DirectoryFd():
    """
    Wrapper for O_DIRECTORY open of a file that allows for automatic closing
    when object is garbage collected.
    """
    def __init__(self, path, dir_fd=None):
        self.__path = path
        self.__dir_fd = None
        self.__dir_fd = os.open(path, os.O_DIRECTORY, dir_fd=dir_fd)

    def __del__(self):
        self.close()

    def __repr__(self):
        return f"<DirectoryFd path='{self.__path}' fileno={self.fileno}>"

    def close(self):
        if self.__dir_fd is None:
            return

        os.close(self.__dir_fd)
        self.__dir_fd = None

    @property
    def fileno(self) -> int:
        return self.__dir_fd


class DirectoryIterator():
    """
    A simple wrapper around os.scandir that provides additional features
    such as statx output, xattr, and acl presence.

    `path` - directory to iterate. `dir_fd` must be specified if relative
    path is used.

    `file_type` - optimization to only yield results of the specified file
    type. Defaults to all file types.

    `request_mask` - bitmask of additional data to include with yielded
    entries. See DirectoryRequestMask. Defaults to _all_ possible attributes.

    `dir_fd` - optional argument to specify an open file descriptor for case
    where we are opening a relative path.

    `as_dict` - yield entries in dictionary expected by `filesystem.listdir`.
    When set to False, then struct_direct (see above) is returned. Default is True

    Context manager protocol is supported and preferred for most cases as it
    will more aggressively free resources.

    ```
    with DirectoryIterator('/mnt') as d_iter:
        for entry in d_iter:
            print(entry)
    ```

    NOTE: this iterator maintains two open files:
    1. the file underlying os.scandir object.
    2. the O_DIRECTORY open of the `path` that was used to create os.scandir
       object. This is required to allow peforming *_at syscalls on directory
       entries.
    """

    def __init__(self, path, file_type=None, request_mask=None, dir_fd=None, as_dict=True):
        self.__dir_fd = None
        self.__path_iter = None
        self.__path = path

        self.__dir_fd = DirectoryFd(path, dir_fd)
        self.__file_type = FileType(file_type).name if file_type else None
        self.__path_iter = os.scandir(self.__dir_fd.fileno)
        self.__stat = statx('', dir_fd=self.__dir_fd.fileno, flags=AT_EMPTY_PATH, mask=STATX_DEFAULT_MASK)

        # Explicitly allow zero for request_mask
        self.__request_mask = request_mask if request_mask is not None else ALL_ATTRS

        self.__return_fn = self.__return_dict if as_dict else self.__return_dirent

    def __repr__(self):
        return (
            f"<DirectoryIterator path='{self.__path}' "
            f"file_type='{'ALL' if self.__file_type is None else self.__file_type}' "
            f"request_mask={self.__request_mask}>"
        )

    def __iter__(self):
        return self

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, tp, value, traceback):
        # Since we know we're leaving scope of context manager
        # we can more aggressively close resources
        self.close(force=True)

    def __check_dir_entry(self, dirent):
        stat_info = statx_entry_impl(pathlib.Path(dirent.name), dir_fd=self.dir_fd)
        if stat_info is None:
            # path doesn't exist anymore
            return None

        if self.__file_type and stat_info['etype'] != self.__file_type:
            # pre-filtering optimization to only select single type of
            # file. This is used by webui to only return directories
            # and reduces cost of any subsequent filtering.
            return None

        return stat_info

    def __return_dirent(self, dirent, st, realpath, xattrs, acl, zfs_attrs, is_in_ctldir):
        """
        More memory-efficient objects for case where dictionary isn't needed or desired.
        """
        return dirent_struct(
            dirent.name,
            os.path.join(self.__path, dirent.name),
            realpath,
            st['st'],
            st['etype'],
            acl,
            xattrs,
            zfs_attrs,
            is_in_ctldir
        )

    def __return_dict(self, dirent, st, realpath, xattrs, acl, zfs_attrs, is_in_ctldir):
        stat = st['st']
        return {
            'name': dirent.name,
            'path': os.path.join(self.__path, dirent.name),
            'realpath': realpath,
            'type': st['etype'],
            'size': stat.stx_size,
            'allocation_size': stat.stx_blocks * 512,
            'mode': stat.stx_mode,
            'acl': acl,
            'uid': stat.stx_uid,
            'gid': stat.stx_gid,
            'mount_id': stat.stx_mnt_id,
            'is_mountpoint': 'MOUNT_ROOT' in st['attributes'],
            'is_ctldir': is_in_ctldir,
            'attributes': st['attributes'],
            'xattrs': xattrs,
            'zfs_attrs': zfs_attrs
        }

    def __next__(self):
        # dirent here is os.DirEntry yielded from os.scandir()
        dirent = next(self.__path_iter)
        while (st := self.__check_dir_entry(dirent)) is None:
            dirent = next(self.__path_iter)

        if self.__request_mask == 0:
            # Skip an unnecessary file open/close if we only need stat info
            return self.__return_fn(dirent, st, None, None, None, None, None)

        try:
            fd = os.open(dirent.name, os.O_RDONLY, dir_fd=self.dir_fd)
        except FileNotFoundError:
            # `dirent` was most likely deleted while we were generating listing
            # There's not point in logging an error. Just keep moving on.
            return self.__next__()
        except OSError as err:
            if err.errno in (errno.ENXIO, errno.ENODEV):
                # this can happen for broken symlinks
                return self.__next__()

            raise

        try:
            if self.__request_mask & int(DirectoryRequestMask.REALPATH):
                realpath = os.path.realpath(f'/proc/self/fd/{fd}')
            else:
                realpath = None

            if self.__request_mask & int(DirectoryRequestMask.XATTRS):
                xattrs = os.listxattr(fd)
            else:
                xattrs = None

            if self.__request_mask & int(DirectoryRequestMask.ACL):
                # try to avoid listing xattrs twice
                acl = acl_is_present(os.listxattr(fd) if xattrs is None else xattrs)
            else:
                acl = None

            if self.__request_mask & int(DirectoryRequestMask.ZFS_ATTRS):
                try:
                    attr_mask = fget_zfs_file_attributes(fd)
                    zfs_attrs = zfs_attributes_dump(attr_mask)
                except OSError as e:
                    # non-ZFS filesystems will fail with ENOTTY or EINVAL
                    # In this case we set `None` to indicate non-ZFS
                    if e.errno not in (errno.ENOTTY, errno.EINVAL):
                        raise e from None

                    zfs_attrs = None
            else:
                zfs_attrs = None

            if self.__request_mask & int(DirectoryRequestMask.CTLDIR):
                is_in_ctldir = path_in_ctldir(os.path.join(self.__path, dirent.name))
            else:
                is_in_ctldir = None

        finally:
            os.close(fd)

        return self.__return_fn(dirent, st, realpath, xattrs, acl, zfs_attrs, is_in_ctldir)

    @property
    def dir_fd(self) -> int:
        """
        File descriptor for O_DIRECTORY open for target directory.
        """
        if self.__dir_fd is None:
            return None

        return self.__dir_fd.fileno

    @property
    def request_mask(self) -> DirectoryRequestMask:
        return self.__request_mask

    @property
    def stat(self) -> StatxResult:
        return self.__stat

    def close(self, force=False) -> None:
        try:
            if self.__path_iter is not None:
                self.__path_iter.close()
                self.__path_iter = None
        except Exception:
            pass

        if self.__dir_fd is not None:
            # decrement reference to __dir_fd and allow
            # garbage collecter to do cleanup. This behavior
            # can be overriden by passing a force parameter
            if force:
                self.__dir_fd.close()

            self.__dir_fd = None


def directory_is_empty(path):
    """
    This is a more memory-efficient way of determining whether a directory is empty
    than looking at os.listdir results.
    """
    with DirectoryIterator(path, request_mask=0, as_dict=False) as d_iter:
        return not any(d_iter)
