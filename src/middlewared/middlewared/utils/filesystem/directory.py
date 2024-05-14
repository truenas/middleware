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
import stat

from collections import namedtuple
from .acl import acl_is_present
from .attrs import fget_zfs_file_attributes, zfs_attributes_dump
from .constants import FileType
from .stat_x import ATFlags, statx, statx_entry_impl
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


class DirectoryRecursionFlag(enum.IntFlag):
    XDEV = enum.auto() # Cross device (ZFS dataset) boundaries
    SEE_CTL = enum.auto() # Include paths within .zfs 


ALL_RECURSION_FLAGS = (
    DirectoryRecursionFlag.XDEV,
    DirectoryRecursionFlag.SEE_CTL
)


dirent_struct = namedtuple('struct_dirent', [
    'name', 'path', 'realpath', 'stat', 'acl', 'xattrs', 'zfs_attrs', 'is_in_ctldir'
])


class DirectoryEntry():
    def __init__(self, parent, dirent, this=None):
        self.__parent = parent
        self.__dirent = dirent
        self.__this_iterator = this

    @property
    def dirent(self):
        return self.__dirent

    @property
    def dir_fd(self):
        if self.__parent is None:
            return None

        return self.__parent.dir_fd

    def skip(self):
        """
        Prune this directory from recursion tree
        """
        self.__this_iterator.close()


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
    def fileno(self):
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

    def __init__(
        self, path, file_type=None, request_mask=None,
        dir_fd=None, as_dict=True, recurse=False, recursion_mask=0
    ):
        self.__dir_fd = None
        self.__path_iter = None
        self.__path = path

        self.__dir_fd = DirectoryFd(path, dir_fd)
        self.__realpath = os.path.realpath(f'/proc/self/fd/{self.dir_fd}')
        self.__file_type = FileType(file_type).name if file_type else None
        self.__path_iter = os.scandir(self.__dir_fd.fileno)
        self.__child_iter = None
        self.__stat = statx('', {'dir_fd': self.__dir_fd.fileno, 'flags': ATFlags.EMPTY_PATH})

        # Explicitly allow zero for request_mask
        self.__request_mask = request_mask if request_mask is not None else ALL_ATTRS

        self.__recursive = recurse
        self.__recursion_mask = recursion_mask

        self.__return_fn = self.__return_dict if as_dict else self.__return_dirent

    def __repr__(self):
        return (
            f"<DirectoryIterator path='{self.__path}' "
            f"file_type='{'ALL' if self.__file_type is None else self.__file_type}' "
            f"recursive={self.__recursive} recursion_mask={self.__recursion_mask} "
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

        if self.__recursion_mask & DirectoryRecursionFlag.XDEV != 0:
            # Check for crossing device boundaries and omit
            if stat_info['st'].stx_mnt_id != self.__stat_info.stx_mnt_id:
                return False

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
            acl,
            xattrs,
            zfs_attrs,
            is_in_ctldir
        )

    def __return_dict(self, dirent, st, realpath, xattrs, acl, zfs_attrs, is_in_ctldir):
        stat_info = st['st']
        return {
            'name': dirent.name,
            'path': os.path.join(self.__path, dirent.name),
            'realpath': realpath,
            'type': st['etype'],
            'size': stat_info.stx_size,
            'allocation_size': stat_info.stx_blocks * 512,
            'mode': stat_info.stx_mode,
            'acl': acl,
            'uid': stat_info.stx_uid,
            'gid': stat_info.stx_gid,
            'mount_id': stat_info.stx_mnt_id,
            'is_mountpoint': 'MOUNT_ROOT' in st['attributes'],
            'is_ctldir': is_in_ctldir,
            'attributes': st['attributes'],
            'xattrs': xattrs,
            'zfs_attrs': zfs_attrs
        }

    def __next__(self):
        # dirent here is os.DirEntry yielded from os.scandir()
        if self.__child_iter is not None:
            try:
                return next(self.__child_iter)
            except StopIteration:
                self.__child_iter.close(force=True)
                self.__child_iter = None
            except Exception as e:
                self.__child_iter.close(force=True)
                self.__child_iter = None

        dirent = next(self.__path_iter)
        while (st := self.__check_dir_entry(dirent)) is None:
            dirent = next(self.__path_iter)

        if self.__recursive and stat.S_ISDIR(st['st'].stx_mode):
            try:
                self.__child_iter = DirectoryIterator(
                    dirent.name, dir_fd=self.__dir_fd.fileno, file_type=self.__file_type,
                    request_mask=self.__request_mask, recurse=True,
                    recursion_mask=self.__recursion_mask, 
                    as_dict=self.__return_fn == self.__return_dict
                )
            except Exception as e:
                print(f"XXX: failed with error: {e}")

        if self.__request_mask == 0:
            # Skip an unnecessary file open/close if we only need stat info
            return self.__return_fn(dirent, st, None, None, None, None, None)

        try:
            fd = os.open(dirent.name, os.O_RDONLY, dir_fd=self.dir_fd)
        except FileNotFoundError:
            # `dirent` was most likely deleted while we were generating listing
            # There's not point in logging an error. Just keep moving on.
            return self.__next__()

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
                    # non-ZFS filesystems will fail with ENOTTY
                    # In this case we set `None` to indicate non-ZFS
                    if e.errno != errno.ENOTTY:
                        raise e from None

                    zfs_attrs = None
            else:
                zfs_attrs = None

            if self.__request_mask & int(DirectoryRequestMask.CTLDIR):
                is_in_ctldir = path_in_ctldir(os.path.join(self.__realpath, dirent.name))
            else:
                is_in_ctldir = None

        finally:
            os.close(fd)

        return self.__return_fn(dirent, st, realpath, xattrs, acl, zfs_attrs, is_in_ctldir)

    @property
    def dir_fd(self):
        """
        File descriptor for O_DIRECTORY open for target directory.
        """
        if self.__dir_fd is None:
            return None

        return self.__dir_fd.fileno

    @property
    def closed(self):
        return self.dir_fd is None

    @property
    def request_mask(self):
        return self.__request_mask

    def close(self, force=False):
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

        while self.__child_iter is not None:
            self.recursion_stop()

    def __get_last_child(self, child, depth, parent):
        """
        Returns tuple of following
        `child` last child in linked iterators

        `depth` current depth in directories

        `parent` parent iterator of child
        """
        if child._DirectoryIterator__child_iter is None:
            return (child, depth, parent)

        return self.__get_last_child(child.__child_iter, depth + 1, parent=child)

    def recursion_stop(self):
        """
        If recusive, stop iterating the current tree
        """
        if not self.__recursive:
            raise ValueError("Not a recursive directory iteration")

        child, depth, parent = self.__get_last_child(self.__child_iter, 1, parent=self)
        child.close(force=True)
        parent._DirectoryIterator__child_iter = None
        

def directory_is_empty(path):
    """
    This is a more memory-efficient way of determining whether a directory is empty
    than looking at os.listdir results.
    """
    with DirectoryIterator(path, request_mask=0, as_dict=False) as d_iter:
        return not any(d_iter)
