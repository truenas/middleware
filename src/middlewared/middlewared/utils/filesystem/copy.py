# Various utilities related to copying / cloning files and file tree
# test coverage provided by pytest/unit/utils/test_copytree.py

import enum
import os

from dataclasses import dataclass
from errno import EXDEV
from middlewared.job import Job
from os import open as posix_open
from os import (
    close,
    copy_file_range,
    fchmod,
    fchown,
    fstat,
    getxattr,
    listxattr,
    lseek,
    makedev,
    mkdir,
    path,
    readlink,
    sendfile,
    setxattr,
    stat_result,
    symlink,
    utime,
    O_CREAT,
    O_DIRECTORY,
    O_EXCL,
    O_NOFOLLOW,
    O_RDONLY,
    O_RDWR,
    O_TRUNC,
    SEEK_CUR,
)
from shutil import copyfileobj
from stat import S_IMODE
from .acl import ACCESS_ACL_XATTRS, ACL_XATTRS
from .directory import (
    dirent_struct,
    DirectoryIterator,
    DirectoryRequestMask,
)
from .stat_x import StatxEtype
from .utils import path_in_ctldir

CLONETREE_ROOT_DEPTH = 0
MAX_RW_SZ = 2147483647 & ~4096  # maximum size of read/write in kernel


class CopyFlags(enum.IntFlag):
    """ Flags specifying which metadata to copy from source to destination """
    XATTRS = 0x0001  # copy user, trusted, security namespace xattrs
    PERMISSIONS = 0x0002  # copy ACL xattrs
    TIMESTAMPS = 0x0004  # copy ACL timestamps
    OWNER = 0x0008


class CopyTreeOp(enum.Enum):
    """
    Available options for customizing the method by which files are copied. DEFAULT
    is generally the best option (prefer to do a block clone and use zero-copy method
    otherwise).

    USERSPACE should be used for certain types of special filesystems such as procfs
    or sysfs that may not properly support copy_file_range or sendfile.
    """
    DEFAULT = enum.auto()  # try clone and fallthrough eventually to userspace
    CLONE = enum.auto()  # attempt to block clone and if that fails, fail operation
    SENDFILE = enum.auto()  # attempt sendfile (with fallthrough to copyfileobj)
    USERSPACE = enum.auto()  # same as shutil.copyfileobj


DEF_CP_FLAGS = CopyFlags.XATTRS | CopyFlags.PERMISSIONS | CopyFlags.OWNER | CopyFlags.TIMESTAMPS


@dataclass(frozen=True, slots=True)
class CopyTreeConfig:
    """
    Configuration for copytree() operation.

    job: middleware Job object. This is optional and may be passed if the API user
        wants to report via job.set_progress

    job_msg_prefix: prefix for progress messages

    job_msg_inc: call set_progress every N files + dirs copied

    raise_error: raise exceptions on metadata copy failures

    exist_ok: do not raise an exception if a file or directory already exists

    traverse: recurse into child datasets

    op: copy tree operation that will be performed (see CopyTreeOp class)

    flags: bitmask of metadata to preserve as part of copy
    """
    job: Job | None = None
    job_msg_prefix: str = ''
    job_msg_inc: int = 1000
    raise_error: bool = True
    exist_ok: bool = True
    traverse: bool = False
    op: CopyTreeOp = CopyTreeOp.DEFAULT
    flags: CopyFlags = DEF_CP_FLAGS  # flags specifying which metadata to copy


@dataclass(slots=True)
class CopyTreeStats:
    dirs: int = 0
    files: int = 0
    symlinks: int = 0
    bytes: int = 0


def _copytree_conf_to_dir_request_mask(config: CopyTreeConfig) -> DirectoryRequestMask:
    """ internal method to convert CopyTreeConfig to a DirectoryRequestMask """
    mask_out = 0
    if config.flags.value & CopyFlags.XATTRS.value:
        mask_out |= DirectoryRequestMask.XATTRS

    if config.flags.value & CopyFlags.PERMISSIONS.value:
        # XATTR list is required for getting preserving ACLs
        mask_out |= DirectoryRequestMask.ACL | DirectoryRequestMask.XATTRS

    return mask_out


def copy_permissions(src_fd: int, dst_fd: int, xattr_list: list[str], mode: int) -> None:
    """ Copy permissions from one file to another.

    Params:
        src_fd: source file
        dst_fd: destination file
        xattr_list: list of all xattrs on src_fd
        mode: POSIX mode of src_fd

    Returns:
        None

    Raises:
        PermissionError: was forced to try to fchmod to set permissions, but destination already
            inherited an ACL and has a RESTRICTED ZFS aclmode.

        OSError - EOPNOTSUPP: ACL type mismatch between src_fd and dst_fd
        OSError: various errnos for reasons specified in syscall manpages for fgetxattr,
            fsetxattr, and fchmod

    NOTE: If source file has an ACL containing permissions then fchmod will not be attempted.
    """
    if not (access_xattrs := set(xattr_list) & ACCESS_ACL_XATTRS):
        # There are no ACLs that encode permissions for _this_ file and so we must use mode

        # NOTE: fchmod will raise PermissionError if ZFS dataset aclmode is RESTRICTED
        # and if the dst_fd inherited an ACL from parent.
        fchmod(dst_fd, S_IMODE(mode))
        return

    for xat_name in access_xattrs:
        xat_buf = getxattr(src_fd, xat_name)
        setxattr(dst_fd, xat_name, xat_buf)


def copy_xattrs(src_fd: int, dst_fd: int, xattr_list: list[str]) -> None:
    """ copy xattrs that aren't for ACLs

    Params:
        src_fd: source file
        dst_fd: destination file
        xattr_list: list of all xattrs on src_fd

    Returns:
        None

    Raises:
        OSError - EOPNOTSUPP: xattr support disabled on the destination filesystem.
        OSError: various errnos for reasons specified in xattr syscall manpages
    """
    for xat_name in set(xattr_list) - ACL_XATTRS:
        if xat_name.startswith('system'):
            # system xattrs typically denote filesystem-specific xattr handlers that
            # may not be applicable to file copies. For now we will skip them silently.
            continue

        xat_buf = getxattr(src_fd, xat_name)
        setxattr(dst_fd, xat_name, xat_buf)


def copy_file_userspace(src_fd: int, dst_fd: int) -> None:
    """ wrapper around copyfilobj that uses file descriptors

    params:
        src_fd: source file
        dst_fd: destination file

    Returns:
        int: bytes written

    Raises:
        Same exceptions as shutil.copyfileobj
        OSError: errno will be set to one of the values specified in
            the manpage for ile_range()
    """
    src = open(src_fd, 'rb', closefd=False)
    dst = open(dst_fd, 'wb', closefd=False)
    copyfileobj(src, dst)

    # TODO: have better method of getting bytes written than fstat on destination.
    return fstat(dst_fd).st_size


def copy_sendfile(src_fd: int, dst_fd: int) -> None:
    """ Optimized copy of file. First try sendfile and if that fails
    perform userspace copy of file.

    params:
        src_fd: source file
        dst_fd: destination file

    Returns:
        int: bytes written

    Raises:
        OSError: errno will be set to one of the values specified in
            the manpage for sendfile()
    """
    offset = 0

    while (sent := sendfile(dst_fd, src_fd, offset, MAX_RW_SZ)) > 0:
        offset += sent

    if offset == 0 and lseek(dst_fd, 0, SEEK_CUR) == 0:
        # maintain fallback code from _fastcopy_sendfile
        return copy_file_userspace(src_fd, dst_fd)

    return offset


def clone_file(src_fd: int, dst_fd: int) -> None:
    """ block cloning is implemented via copy_file_range

    params:
        src_fd: source file
        dst_fd: destination file

    Returns:
        int: bytes written

    Raises:
        OSError: EXDEV (zfs) source and destination are on different pools.
        OSError: EXDEV (non-zfs) source and destination are on filesystems.
        OSError: errno will be set to one of the values specified in
            the manpage for copy_file_range()
    """
    offset = 0

    # loop until copy_file_range returns 0 catch any possible TOCTOU issues
    # that may arrive if data added after initial statx call.
    while (copied := copy_file_range(
            src_fd, dst_fd,
            MAX_RW_SZ,
            offset_src=offset,
            offset_dst=offset
    )) > 0:
        offset += copied

    return offset


def clone_or_copy_file(src_fd: int, dst_fd: int) -> None:
    """ try to clone file via copy_file_range and if fails fall back to
    shutil.copyfileobj

    params:
        src_fd: source file
        dst_fd: destination file

    Returns:
        int: bytes written

    Raises:
        OSError
    """
    try:
        return clone_file(src_fd, dst_fd)
    except OSError as err:
        if err.errno == EXDEV:
            # different pool / non-zfs
            return copy_sendfile(src_fd, dst_fd)

        # Other error
        raise


def _do_mkfile(
    src: dirent_struct,
    src_fd: int,
    dst_fd: int,
    config: CopyTreeConfig,
    stats: CopyTreeStats,
    c_fn: callable
) -> None:
    """ Perform copy / clone of file, possibly preserving metadata.

    Params:
        src: direct_struct of parent directory of the src_fd
        src_fd: handle of file being copied
        dst_fd: handle of target file
        config: configuration of the copy operation
        stats: counters to be update with bytes written
        c_fn: the copy / clone function to use for writing data to the destination

    Returns:
        None

    Raises:
        OSError
        PermissionError

    NOTE: this is an internal method that should only be called from within copytree.
    """
    if config.flags.value & CopyFlags.PERMISSIONS.value:
        try:
            copy_permissions(src_fd, dst_fd, src.xattrs, src.stat.stx_mode)
        except Exception:
            if config.raise_error:
                raise

    if config.flags.value & CopyFlags.XATTRS.value:
        try:
            copy_xattrs(src_fd, dst_fd, src.xattrs)
        except Exception:
            if config.raise_error:
                raise

    if config.flags.value & CopyFlags.OWNER.value:
        fchown(dst_fd, src.stat.stx_uid, src.stat.stx_gid)

    stats.bytes += c_fn(src_fd, dst_fd)

    # We need to write timestamps after file data to ensure reset atime / mtime
    if config.flags.value & CopyFlags.TIMESTAMPS.value:
        ns_ts = (src.stat.stx_atime_ns, src.stat.stx_mtime_ns)
        try:
            utime(dst_fd, ns=ns_ts)
        except Exception:
            if config.raise_error:
                raise


def _do_mkdir(
    src: dirent_struct,
    src_fd: int,
    dst_dir_fd: int,
    config: CopyTreeConfig
) -> int:
    """ Internal method to mkdir and set its permissions and xattrs

    Params:
        src: direct_struct of parent directory of the src_fd
        src_fd: handle of file being copied
        dst_fd: handle of target file
        config: configuration of the copy operation
        c_fn: the copy / clone function to use for writing data to the destination

    Returns:
        file descriptor

    Raises:
        OSError

    NOTE: this is an internal method that should only be called from within copytree.
    """
    try:
        mkdir(src.name, dir_fd=dst_dir_fd)
    except FileExistsError:
        if not config.exist_ok:
            raise

    new_dir_hdl = posix_open(src.name, O_DIRECTORY, dir_fd=dst_dir_fd)
    try:
        if config.flags.value & CopyFlags.PERMISSIONS.value:
            copy_permissions(src_fd, new_dir_hdl, src.xattrs, src.stat.stx_mode)

        if config.flags.value & CopyFlags.XATTRS.value:
            copy_xattrs(src_fd, new_dir_hdl, src.xattrs)

        if config.flags.value & CopyFlags.OWNER.value:
            fchown(new_dir_hdl, src.stat.stx_uid, src.stat.stx_gid)

    except Exception:
        if config.raise_error:
            close(new_dir_hdl)
            raise

    return new_dir_hdl


def _copytree_impl(
    d_iter: DirectoryIterator,
    dst_str: str,
    dst_fd: int,
    depth: int,
    config: CopyTreeConfig,
    target_st: stat_result,
    stats: CopyTreeStats
):
    """ internal implementation of our copytree method

    NOTE: this method is called recursively for each directory to walk down tree.
    This means additional O_DIRECTORY open for duration of life of each DirectoryIterator
    object (closed when DirectoryIterator context manager exits).

    Params:
        d_iter: directory iterator for current directory
        dst_str: target directory of copy
        dst_fd: open file handle for target directory
        depth: current depth in src directory tree
        config: CopyTreeConfig - used to determine what to copy
        target_st: stat_result of target directory for initial copy. This is used
            to provide device + inode number so that we can avoid copying destination into
            itself.

    Returns:
        None

    Raises:
        OSError
        PermissionError
    """

    match config.op:
        case CopyTreeOp.DEFAULT:
            c_fn = clone_or_copy_file
        case CopyTreeOp.CLONE:
            c_fn = clone_file
        case CopyTreeOp.SENDFILE:
            c_fn = copy_sendfile
        case CopyTreeOp.USERSPACE:
            c_fn = copy_file_userspace
        case _:
            raise ValueError(f'{config.op}: unexpected copy operation')

    for entry in d_iter:
        # We match on `etype` key because our statx wrapper will initially lstat a file
        # and if it's a symlink, perform a stat call to get information from symlink target
        # This means that S_ISLNK on mode will fail to detect whether it's a symlink.
        match entry.etype:
            case StatxEtype.DIRECTORY.name:
                if not config.traverse:
                    if entry.stat.stx_mnt_id != d_iter.stat.stx_mnt_id:
                        # traversal is disabled and entry is in different filesystem
                        # continue here prevents entering the directory / filesystem
                        continue

                if entry.name == '.zfs':
                    # User may have visible snapdir. We definitely don't want to try to copy this
                    # path_in_ctldir checks inode number to verify it's not reserved number for
                    # these special paths (definitive indication it's ctldir as opposed to random
                    # dir user named '.zfs')
                    if path_in_ctldir(entry.path):
                        continue

                if entry.stat.stx_ino == target_st.st_ino:
                    # We use makedev / dev_t in this case to catch potential edge cases where bind mount
                    # in path (since bind mounts of same filesystem will have same st_dev, but different
                    # stx_mnt_id.
                    if makedev(entry.stat.stx_dev_major, entry.stat.stx_dev_minor) == target_st.st_dev:
                        continue

                # This can fail with OSError and errno set to ELOOP if target was maliciously
                # replaced with symlink between our first stat and the open call
                entry_fd = posix_open(entry.name, O_DIRECTORY | O_NOFOLLOW, dir_fd=d_iter.dir_fd)
                try:
                    new_dst_fd = _do_mkdir(entry, entry_fd, dst_fd, config)
                except Exception:
                    close(entry_fd)
                    raise

                # We made directory on destination and copied metadata for it, and so we're safe
                # to recurse into it in source and continue our operation.
                try:
                    with DirectoryIterator(
                        entry.name,
                        request_mask=d_iter.request_mask,
                        dir_fd=d_iter.dir_fd,
                        as_dict=False
                    ) as c_iter:
                        _copytree_impl(
                            c_iter,
                            path.join(dst_str, entry.name),
                            new_dst_fd,
                            depth + 1,
                            config,
                            target_st,
                            stats
                        )

                    if config.flags.value & CopyFlags.TIMESTAMPS.value:
                        ns_ts = (entry.stat.stx_atime_ns, entry.stat.stx_mtime_ns)
                        try:
                            utime(new_dst_fd, ns=ns_ts)
                        except Exception:
                            if config.raise_error:
                                raise

                finally:
                    close(new_dst_fd)
                    close(entry_fd)

                stats.dirs += 1

            case StatxEtype.FILE.name:
                entry_fd = posix_open(entry.name, O_RDONLY | O_NOFOLLOW, dir_fd=d_iter.dir_fd)
                try:
                    flags = O_RDWR | O_NOFOLLOW | O_CREAT | O_TRUNC
                    if not config.exist_ok:
                        flags |= O_EXCL

                    dst = posix_open(entry.name, flags, dir_fd=dst_fd)
                    try:
                        _do_mkfile(entry, entry_fd, dst, config, stats, c_fn)
                    finally:
                        close(dst)
                finally:
                    close(entry_fd)

                stats.files += 1

            case StatxEtype.SYMLINK.name:
                stats.symlinks += 1
                dst = readlink(entry.name, dir_fd=d_iter.dir_fd)
                try:
                    symlink(dst, entry.name, dir_fd=dst_fd)
                except FileExistsError:
                    if not config.exist_ok:
                        raise

                continue

            case _:
                continue

        if config.job and ((stats.dirs + stats.files) % config.job_msg_inc) == 0:
            config.job.set_progress(100, (
                f'{config.job_msg_prefix}'
                f'Copied {entry.path} -> {os.path.join(dst_str, entry.name)}.'
            ))


def copytree(
    src: str,
    dst: str,
    config: CopyTreeConfig
) -> CopyTreeStats:
    """
    Copy all files, directories, and symlinks from src to dst. CopyTreeConfig allows
    controlling whether we recurse into child datasets on src side as well as specific
    metadata to preserve in the copy. This method also has protection against copying
    the zfs snapshot directory if for some reason the user has set it to visible.

    Params:
        src: the source directory
        dst: the destination directory
        config: configuration parameters for the copy

    Returns:
        CopyStats

    Raises:
        OSError: ELOOP: path was replaced with symbolic link while recursing
            this should never happen during normal operations and may indicate
            an attempted symlink attack
        OSError: EOPNOTSUPP: ACL type mismatch between src and dst
        OSError: EOPNOTSUPP: xattrs are disabled on dst
        OSError: <generic>: various reasons listed in syscall manpages
        PermissionError:
            Attempt to chmod on destination failed due to RESTRICTED aclmode on dataset.

    """
    for p in (src, dst):
        if not path.isabs(p):
            raise ValueError(f'{p}: absolute path is required')

    dir_request_mask = _copytree_conf_to_dir_request_mask(config)
    try:
        os.mkdir(dst)
    except FileExistsError:
        if not config.exist_ok:
            raise

    dst_fd = posix_open(dst, O_DIRECTORY)

    stats = CopyTreeStats()

    try:
        with DirectoryIterator(src, request_mask=int(dir_request_mask), as_dict=False) as d_iter:
            _copytree_impl(d_iter, dst, dst_fd, CLONETREE_ROOT_DEPTH, config, fstat(dst_fd), stats)

            # Ensure that root level directory also gets metadata copied
            try:
                xattrs = listxattr(d_iter.dir_fd)
                if config.flags.value & CopyFlags.PERMISSIONS.value:
                    copy_permissions(d_iter.dir_fd, dst_fd, xattrs, d_iter.stat.stx_mode)

                if config.flags.value & CopyFlags.XATTRS.value:
                    copy_xattrs(d_iter.dir_fd, dst_fd, xattrs)

                if config.flags.value & CopyFlags.OWNER.value:
                    fchown(dst_fd, d_iter.stat.stx_uid, d_iter.stat.stx_gid)

                if config.flags.value & CopyFlags.TIMESTAMPS.value:
                    ns_ts = (d_iter.stat.stx_atime_ns, d_iter.stat.stx_mtime_ns)
                    utime(dst_fd, ns=ns_ts)
            except Exception:
                if config.raise_error:
                    raise

    finally:
        close(dst_fd)

    if config.job:
        config.job.set_progress(100, (
            f'{config.job_msg_prefix}'
            f'Successfully copied {stats.dirs} directories, {stats.files} files, '
            f'{stats.symlinks} symlinks for a total of {stats.bytes} bytes of data.'
        ))

    return stats
