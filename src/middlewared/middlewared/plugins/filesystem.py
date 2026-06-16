from __future__ import annotations

import binascii
from collections.abc import Generator
import errno
import functools
from itertools import product
import os
import pathlib
import shutil
import stat as statlib
import time
from typing import IO, TYPE_CHECKING, Any, Iterable, Literal, Sequence

import pyinotify
import truenas_os
from truenas_os_pyutils.io import safe_open
from truenas_os_pyutils.mount import StatmountResultDict, iter_mountinfo, statmount

from middlewared.api import api_method, private_method
from middlewared.api.base import (
    BaseModel,
    LongNonEmptyString,
    NonEmptyString,
)
from middlewared.api.current import (
    FileFollowTailEventSourceArgs,
    FileFollowTailEventSourceEvent,
    FilesystemDirEntry,
    FilesystemGetArgs,
    FilesystemGetResult,
    FilesystemGetZfsAttributesArgs,
    FilesystemGetZfsAttributesResult,
    FilesystemListdirArgs,
    FilesystemListdirResult,
    FilesystemListdirResultItem,
    FilesystemMkdirArgs,
    FilesystemMkdirData,
    FilesystemMkdirResult,
    FilesystemPutArgs,
    FilesystemPutOptions,
    FilesystemPutResult,
    FilesystemSetZfsAttributesArgs,
    FilesystemSetZfsAttributesData,
    FilesystemSetZfsAttributesResult,
    FilesystemStatArgs,
    FilesystemStatData,
    FilesystemStatfsArgs,
    FilesystemStatfsData,
    FilesystemStatfsResult,
    FilesystemStatResult,
    QueryFilters,
    QueryOptions,
    ZFSFileAttrsData,
)
from middlewared.event import TypedEventSource
from middlewared.plugins.account_.constants import SYNTHETIC_CONTAINER_ROOT
from middlewared.plugins.docker.state_utils import IX_APPS_DIR_NAME
from middlewared.plugins.filesystem_.utils import apply_zfs_attrs_recursive
from middlewared.service import CallError, Service, ValidationErrors, filterable_api_method, job, private
from middlewared.utils.filesystem import attrs, stat_x
from middlewared.utils.filesystem.acl import ACL_UNDEFINED_ID, acl_is_present
from middlewared.utils.filesystem.constants import FileType
from middlewared.utils.filesystem.directory import DirectoryRequestMask, iter_listdir
from middlewared.utils.filter_list import filter_list, filter_list_model
from middlewared.utils.nss import grp, pwd
from middlewared.utils.path import FSLocation, is_child_realpath, path_location
from middlewared.utils.pwenc import PWENC_FILE_SECRET

if TYPE_CHECKING:
    from middlewared.job import Job


class FilesystemReceiveFileOptions(BaseModel):
    append: bool = False
    mode: int | None = None
    uid: int = ACL_UNDEFINED_ID
    gid: int = ACL_UNDEFINED_ID


class FilesystemReceiveFileArgs(BaseModel):
    path: NonEmptyString
    content: LongNonEmptyString
    options: FilesystemReceiveFileOptions = FilesystemReceiveFileOptions()


class FilesystemReceiveFileResult(BaseModel):
    result: Literal[True]


class FileFollowTailEventSource(TypedEventSource[FileFollowTailEventSourceArgs]):
    """
    Retrieve last ``tail_lines`` lines specified as an integer argument for a specified ``path`` and then
    any new lines as they are added.
    """
    args = FileFollowTailEventSourceArgs
    event = FileFollowTailEventSourceEvent

    def run_sync(self) -> None:
        path, lines = self.typed_arg.path, self.typed_arg.tail_lines

        if not os.path.exists(path):
            # FIXME: Error?
            return

        bufsize = 8192
        fsize = os.stat(path).st_size
        if fsize < bufsize:
            bufsize = fsize
        i = 0
        with safe_open(path, encoding='utf-8', errors='ignore') as f:
            data = []
            while True:
                i += 1
                if bufsize * i > fsize:
                    break
                f.seek(fsize - bufsize * i)
                data.extend(f.readlines())
                if len(data) >= lines or f.tell() == 0:
                    break

            self.send_event('ADDED', fields={'data': ''.join(data[-lines:])})
            f.seek(fsize)

            for chunk in self._follow_path(path, f):
                self.send_event('ADDED', fields={'data': chunk})

    def _follow_path(self, path: str, f: IO[str]) -> Generator[str, None, None]:
        queue: list[str] = []
        watch_manager = pyinotify.WatchManager()
        notifier = pyinotify.Notifier(watch_manager)
        watch_manager.add_watch(path, pyinotify.IN_MODIFY, functools.partial(self._follow_callback, queue, f))

        data = f.read()
        if data:
            yield data

        last_sent_at = time.monotonic()
        interval = 0.5  # For performance reasons do not send websocket events more than twice a second
        while not self._cancel_sync.is_set():
            notifier.process_events()

            if time.monotonic() - last_sent_at >= interval:
                data = "".join(queue)
                if data:
                    yield data
                queue[:] = []
                last_sent_at = time.monotonic()

            if notifier.check_events(timeout=int(interval * 1000)):
                notifier.read_events()

        notifier.stop()

    def _follow_callback(self, queue: list[str], f: IO[str], event: Any) -> None:
        data = f.read()
        if data:
            queue.append(data)


class FilesystemService(Service):

    class Config:
        cli_private = True
        event_sources = {
            'filesystem.file_tail_follow': FileFollowTailEventSource,
        }

    @api_method(
        FilesystemSetZfsAttributesArgs, FilesystemSetZfsAttributesResult,
        roles=['FILESYSTEM_ATTRS_WRITE'],
        audit='Filesystem set ZFS attributes',
        audit_extended=lambda data: data['path'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'zfs_attrs_change:{args[0]["path"]}')
    def set_zfs_attributes(self, job: Job, data: FilesystemSetZfsAttributesData) -> ZFSFileAttrsData:
        """
        Set special ZFS-related file flags on the specified path.

        `readonly` - READONLY MS-DOS attribute. When set, file may not be written to
        (toggling does not impact existing file opens).

        `hidden` - HIDDEN MS-DOS attribute. When set, the SMB HIDDEN flag is set and
        file is "hidden" from the perspective of SMB clients.

        `system` - SYSTEM MS-DOS attribute. Is presented to SMB clients, but has no
        impact on local filesystem.

        `archive` - ARCHIVE MS-DOS attribute. Value is reset to True whenever file is
        modified.

        `immutable` - file may not be altered or deleted. Also appears as IMMUTABLE in
        attributes in `filesystem.stat` output and as STATX_ATTR_IMMUTABLE in statx().

        `nounlink` - file may be altered but not deleted.

        `appendonly` - file may only be opened with O_APPEND flag. Also appears as
        APPEND in attributes in `filesystem.stat` output and as STATX_ATTR_APPEND in
        statx() response.

        `offline` - OFFLINE MS-DOS attribute. Is presented to SMB clients, but has no
        impact on local filesystem.

        `sparse` - SPARSE MS-DOS attribute. Is presented to SMB clients, but has no
        impact on local filesystem.

        `options.recursive` - if set to a non-empty list of `FILES`/`DIRECTORIES`,
        the path is treated as the root of a tree walk and attributes are applied to
        descendants of the matching type. The root `path` itself is included only if
        its type matches the filter. `null` (the default) preserves the legacy
        single-path behavior. Recursion stops at dataset boundaries.
        """
        recursive = data.options.recursive
        if recursive is not None and len(recursive) == 0:
            verrors = ValidationErrors()
            verrors.add(
                'filesystem.set_zfs_attributes.options.recursive',
                'Must be null or a non-empty list of FILES/DIRECTORIES.',
            )
            verrors.check()

        job.set_progress(0, 'Setting ZFS attributes')
        try:
            if recursive is None:
                # Legacy single-path semantics — cheap path, no walker.
                return ZFSFileAttrsData(
                    **attrs.set_zfs_file_attributes_dict(data.path, data.zfs_file_attributes.model_dump()),
                )

            try:
                fd = truenas_os.openat2(data.path, os.O_RDWR, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
                is_dir = False
            except IsADirectoryError:
                fd = truenas_os.openat2(data.path, os.O_DIRECTORY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
                is_dir = True

            try:
                return apply_zfs_attrs_recursive(fd, is_dir, data.zfs_file_attributes, recursive, job=job)
            finally:
                os.close(fd)
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise CallError('Symlinks are not permitted.', errno.ELOOP)
            raise

    @api_method(
        FilesystemGetZfsAttributesArgs,
        FilesystemGetZfsAttributesResult,
        roles=['FILESYSTEM_ATTRS_READ'],
        check_annotations=True,
    )
    def get_zfs_attributes(self, path: str) -> ZFSFileAttrsData:
        """
        Get the current ZFS attributes for the file at the given path
        """
        try:
            fd = truenas_os.openat2(path, os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise CallError('Symlinks are not permitted.', errno.ELOOP)
            raise
        try:
            attr_mask = attrs.fget_zfs_file_attributes(fd)
        finally:
            os.close(fd)

        return ZFSFileAttrsData(**attrs.zfs_attributes_to_dict(attr_mask))

    @private_method()
    def is_child(self, child: str | list[str], parent: str | list[str]) -> bool:
        for to_check in product(
            child if isinstance(child, list) else [child],
            parent if isinstance(parent, list) else [parent]
        ):
            if is_child_realpath(to_check[0], to_check[1]):
                return True

        return False

    @private_method()
    def is_dataset_path(self, path: str) -> bool:
        return path.startswith('/mnt/') and os.stat(path).st_dev != os.stat('/mnt').st_dev

    @filterable_api_method(private=True)
    def mount_info(
        self,
        filters: Iterable[Sequence[Any]],
        options: dict[str, Any],
    ) -> list[StatmountResultDict] | StatmountResultDict | int:
        return filter_list(iter_mountinfo(), filters, options)

    @api_method(FilesystemMkdirArgs, FilesystemMkdirResult, roles=['FILESYSTEM_DATA_WRITE'], check_annotations=True)
    def mkdir(self, data: FilesystemMkdirData) -> FilesystemDirEntry:
        """
        Create a directory at the specified path.

        The following options are supported:

        `mode` - specify the permissions to set on the new directory (0o755 is default).
        `raise_chmod_error` - choose whether to raise an exception if the attempt to set
        mode fails. In this case, the newly created directory will be removed to prevent
        use with unintended permissions.

        NOTE: if chmod error is skipped, the resulting `mode` key in mkdir response will
        indicate the current permissions on the directory and not the permissions specified
        in the mkdir payload
        """
        mode = int(data.options.mode, 8)

        p = pathlib.Path(data.path)
        if not p.is_absolute():
            raise CallError(f'{data.path}: not an absolute path.', errno.EINVAL)

        if p.exists():
            raise CallError(f'{data.path}: path already exists.', errno.EEXIST)

        # Resolve the parent with no symlink follow and operate via dir_fd, so the
        # prefix check below cannot be raced against the mkdir.
        parent = os.path.dirname(data.path) or '/'
        basename = os.path.basename(data.path)
        try:
            parent_fd = truenas_os.openat2(
                parent, os.O_DIRECTORY,
                resolve=truenas_os.RESOLVE_NO_SYMLINKS,
            )
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise CallError(f'{data.path}: symlinks in path are not permitted', errno.EPERM)
            if e.errno == errno.ENOENT:
                raise CallError(f'{data.path}: parent directory does not exist', errno.ENOENT)
            raise

        try:
            realpath = os.path.join(os.readlink(f'/proc/self/fd/{parent_fd}'), basename)
            if not realpath.startswith(('/mnt/', '/root/.ssh', '/home/admin/.ssh', '/home/truenas_admin/.ssh')):
                raise CallError(f'{data.path}: path not permitted', errno.EPERM)

            os.mkdir(basename, mode=mode, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)

        st = stat_x.statx_entry_impl(p)
        if st is None:
            raise CallError(f'{data.path}: statx entry does not exist', errno.ENOENT)

        stat = st['st']

        if statlib.S_IMODE(stat.stx_mode) != mode:
            # This may happen if requested mode is greater than umask
            # or if underlying dataset has restricted aclmode and ACL is present
            try:
                os.chmod(data.path, mode)
            except Exception:
                if data.options.raise_chmod_error:
                    os.rmdir(data.path)
                    raise

                self.logger.debug(
                    '%s: failed to set mode %s on path after mkdir call',
                    data.path, data.options.mode, exc_info=True
                )

        return FilesystemDirEntry(
            name=p.parts[-1],
            path=data.path,
            realpath=realpath,
            type='DIRECTORY',
            size=stat.stx_size,
            allocation_size=stat.stx_blocks * 512,
            mode=stat.stx_mode,
            acl=acl_is_present(os.listxattr(data.path)),
            uid=stat.stx_uid,
            gid=stat.stx_gid,
            is_mountpoint=False,
            is_ctldir=False,
            mount_id=st['st'].stx_mnt_id,
            attributes=st['attributes'],
            xattrs=[],
            zfs_attrs=['ARCHIVE'],
        )

    @private
    def listdir_request_mask(self, select: list[str | list[str]] | None) -> DirectoryRequestMask | None:
        """ create request mask for directory listing """
        if not select:
            # request_mask=None means ALL in the directory iterator
            return None

        request_mask = DirectoryRequestMask(0)
        for i in select:
            # select may be list [key, new_name] to allow
            # equivalent of SELECT AS.
            selected = i[0] if isinstance(i, list) else i

            match selected:
                case 'realpath':
                    request_mask |= DirectoryRequestMask.REALPATH
                case 'acl':
                    request_mask |= DirectoryRequestMask.ACL
                case 'zfs_attrs':
                    request_mask |= DirectoryRequestMask.ZFS_ATTRS
                case 'is_ctldir':
                    request_mask |= DirectoryRequestMask.CTLDIR
                case 'xattrs':
                    request_mask |= DirectoryRequestMask.XATTRS

        return request_mask

    @api_method(FilesystemListdirArgs, FilesystemListdirResult, roles=['FILESYSTEM_ATTRS_READ'], check_annotations=True)
    def listdir(
        self,
        path: str,
        filters: QueryFilters,
        options: QueryOptions,
    ) -> list[FilesystemListdirResultItem] | FilesystemListdirResultItem | int:
        """
        Get the contents of a directory.

        The select option may be used to optimize listdir performance. Metadata-related
        fields that are not selected will not be retrieved from the filesystem.

        For example {"select": ["path", "type"]} will avoid querying an xattr list and
        ZFS attributes for files in a directory.

        """
        p = pathlib.Path(path)
        if not p.exists():
            raise CallError(f'Directory {path} does not exist', errno.ENOENT)

        if not p.is_dir():
            raise CallError(f'Path {path} is not a directory', errno.ENOTDIR)

        request_mask: DirectoryRequestMask | None
        if options.count:
            # We're just getting count, drop any unnecessary info
            request_mask = DirectoryRequestMask(0)
        else:
            request_mask = self.listdir_request_mask(options.select)

        # None request_mask means "everything"
        if request_mask is None or (request_mask & DirectoryRequestMask.ZFS_ATTRS):
            # Make sure this is actually ZFS before issuing FS ioctls
            try:
                self.get_zfs_attributes(str(p))
            except CallError:
                raise
            except Exception:
                raise CallError(f'{path}: ZFS attributes are not supported.')

        file_type = None
        for filter_ in filters:
            if filter_[0] not in ['type']:
                continue

            if filter_[1] != '=':
                continue

            if filter_[2] == 'DIRECTORY':
                file_type = FileType.DIRECTORY
            elif filter_[2] == 'FILE':
                file_type = FileType.FILE
            else:
                continue

        if p.absolute() == pathlib.Path('/mnt'):
            # sometimes (on failures) the top-level directory
            # where the zpool is mounted does not get removed
            # after the zpool is exported. WebUI calls this
            # specifying `/mnt` as the path. This is used when
            # configuring shares in the "Path" drop-down. To
            # prevent shares from being configured to point to
            # a path that doesn't exist on a zpool, we'll
            # filter these here.
            filters.extend([['is_mountpoint', '=', True], ['name', '!=', IX_APPS_DIR_NAME]])

        return filter_list_model(filter_list(
            iter_listdir(p, file_type=file_type, request_mask=request_mask),
            filters,
            options.model_dump(),
        ), FilesystemListdirResultItem)

    @api_method(FilesystemStatArgs, FilesystemStatResult, roles=['FILESYSTEM_ATTRS_READ'], check_annotations=True)
    def stat(self, _path: str) -> FilesystemStatData:
        """
        Return filesystem information for a given path.

        `realpath(str)`: absolute real path of the entry (if SYMLINK)

        `type(str)`: DIRECTORY | FILE | SYMLINK | OTHER

        `size(int)`: size of the entry

        `allocation_size(int)`: on-disk size of entry

        `mode(int)`: file mode/permission

        `uid(int)`: user id of file owner

        `gid(int)`: group id of file owner

        `atime(float)`: timestamp for when file was last accessed.
        NOTE: this timestamp may be changed from userspace.

        `mtime(float)`: timestamp for when file data was last modified
        NOTE: this timestamp may be changed from userspace.

        `ctime(float)`: timestamp for when file was last changed.

        `btime(float)`: timestamp for when file was initially created.
        NOTE: depending on platform this may be changed from userspace.

        `dev(int)`: device id of the device containing the file. In the
        context of the TrueNAS API, this is sufficient to uniquely identify
        a given dataset.

        `mount_id(int)`: the mount id for the filesystem underlying the given path.
        Bind mounts will have same device id, but different mount IDs. This value
        is sufficient to uniquely identify the particular mount which can be used
        to identify children of the given mountpoint.

        `inode(int)`: inode number of the file. This number uniquely identifies
        the file on the given device, but once a file is deleted its inode number
        may be reused.

        `nlink(int)`: number of hard lnks to the file.

        `acl(bool)`: extended ACL is present on file

        `is_mountpoint(bool)`: path is a mountpoint

        `is_ctldir(bool)`: path is within special .zfs directory

        `attributes(list)`: list of statx file attributes that apply to the
        file. See statx(2) manpage for more details.
        """
        if path_location(_path) is FSLocation.EXTERNAL:
            raise CallError(f'{_path} is external to TrueNAS', errno.EXDEV)

        path = pathlib.Path(_path)
        if not path.is_absolute():
            raise CallError(f'{_path}: path must be absolute', errno.EINVAL)

        st = stat_x.statx_entry_impl(path)
        if st is None:
            raise CallError(f'Path {_path} not found', errno.ENOENT)

        realpath = path.resolve().as_posix() if st['etype'] == 'SYMLINK' else path.absolute().as_posix()

        try:
            user: str | None = pwd.getpwuid(st['st'].stx_uid).pw_name
        except KeyError:
            if st['st'].stx_uid == SYNTHETIC_CONTAINER_ROOT['pw_uid']:
                user = SYNTHETIC_CONTAINER_ROOT['pw_name']  # type: ignore[assignment]
            else:
                user = None

        try:
            group = grp.getgrgid(st['st'].stx_gid).gr_name
        except KeyError:
            group = None

        return FilesystemStatData(
            realpath=realpath,
            type=st['etype'],
            size=st['st'].stx_size,
            allocation_size=st['st'].stx_blocks * 512,
            mode=st['st'].stx_mode,
            uid=st['st'].stx_uid,
            gid=st['st'].stx_gid,
            atime=st['st'].stx_atime,
            mtime=st['st'].stx_mtime,
            ctime=st['st'].stx_ctime,
            btime=st['st'].stx_btime,
            mount_id=st['st'].stx_mnt_id,
            dev=st['st'].stx_dev,
            inode=st['st'].stx_ino,
            nlink=st['st'].stx_nlink,
            is_mountpoint='MOUNT_ROOT' in st['attributes'],
            is_ctldir=st['is_ctldir'],
            attributes=st['attributes'],
            user=user,
            group=group,
            acl=acl_is_present(os.listxattr(path)),
        )

    # WARNING: following method cannot currently be audited properly due to RFC limitations on
    # syslog message size.
    @api_method(FilesystemReceiveFileArgs, FilesystemReceiveFileResult, private=True, check_annotations=True)
    def file_receive(self, path: str, content: str, options: FilesystemReceiveFileOptions) -> Literal[True]:
        """
        Simplified file receiving method for small files.

        `content` must be a base 64 encoded file content.
        """
        if path == PWENC_FILE_SECRET:
            raise CallError(
                'Cannot use filesystem.put to write pwenc secret. Use pwenc.replace instead.',
                errno.EINVAL
            )

        dirname = os.path.dirname(path)
        # NOTE: os.makedirs follows symlinks, so an attacker could cause directories
        # to be created at symlink target locations as a side effect. The subsequent
        # safe_open blocks the actual file write via RESOLVE_NO_SYMLINKS, but the
        # created directories are not rolled back. Fully safe directory creation
        # would require an fd-walking mkdirat implementation.
        os.makedirs(dirname, exist_ok=True)

        with safe_open(path, 'ab' if options.append else 'wb+') as f:
            f.write(binascii.a2b_base64(content))
            if mode := options.mode:
                os.fchmod(f.fileno(), mode)
            # -1 means don't change uid/gid if the one provided is
            # the same that is on disk already
            os.fchown(f.fileno(), options.uid, options.gid)
            f.flush()

        return True

    @api_method(
        FilesystemGetArgs,
        FilesystemGetResult,
        audit='Filesystem get',
        roles=['FULL_ADMIN'],
        check_annotations=True,
    )
    @job(pipes=["output"])
    def get(self, job: Job, path: str) -> None:
        """
        Job to get contents of `path`.
        """
        assert job.pipes.output is not None

        if not os.path.isfile(path):
            raise CallError(f'{path} is not a file')

        with safe_open(path, 'rb') as f:
            shutil.copyfileobj(f, job.pipes.output.w)

    @api_method(
        FilesystemPutArgs,
        FilesystemPutResult,
        audit='Filesystem put',
        roles=['FULL_ADMIN'],
        check_annotations=True,
    )
    @job(pipes=["input"])
    def put(self, job: Job, path: str, options: FilesystemPutOptions) -> Literal[True]:
        """
        Job to put contents to `path`.
        """
        if path == PWENC_FILE_SECRET:
            raise CallError(
                'Cannot use filesystem.put to write pwenc secret. Use pwenc.replace instead.',
                errno.EINVAL
            )

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            # NOTE: os.makedirs follows symlinks, so an attacker could cause directories
            # to be created at symlink target locations as a side-effect. The subsequent
            # safe_open blocks the actual file write via RESOLVE_NO_SYMLINKS, but the
            # created directories are not rolled back. Fully safe directory creation
            # would require an fd-walking mkdirat implementation.
            os.makedirs(dirname)
        if options.append:
            openmode = 'ab'
        else:
            openmode = 'wb+'

        try:
            with safe_open(path, openmode) as f:
                if options.mode:
                    os.fchmod(f.fileno(), options.mode)

                shutil.copyfileobj(job.pipes.input.r, f)
        except PermissionError:
            raise CallError(f'Unable to put contents at {path!r} as the path exists on a locked dataset', errno.EINVAL)

        return True

    @api_method(FilesystemStatfsArgs, FilesystemStatfsResult, roles=['FILESYSTEM_ATTRS_READ'], check_annotations=True)
    def statfs(self, path: str) -> FilesystemStatfsData:
        """
        Return stats from the filesystem of a given path.

        If ``path`` does not exist, the method raises a ``CallError`` (code ``-32001``, *Method call error*).
        """
        try:
            fd = truenas_os.openat2(path, os.O_PATH, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
            try:
                st = os.fstatvfs(fd)
                mntinfo = statmount(fd=fd)
            finally:
                os.close(fd)

        except FileNotFoundError:
            raise CallError('Path not found.', errno.ENOENT)
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise CallError('Symlinks are not permitted.', errno.ELOOP)
            raise

        flags = mntinfo['mount_opts']
        for flag in mntinfo['super_opts']:
            if flag in flags:
                continue
            flags.append(flag)

        return FilesystemStatfsData(
            flags=flags,
            fstype=(mntinfo['fs_type'] or '').lower(),
            source=mntinfo['mount_source'],
            dest=mntinfo['mountpoint'],
            blocksize=st.f_frsize,
            total_blocks=st.f_blocks,
            total_blocks_str=str(st.f_blocks),
            free_blocks=st.f_bfree,
            free_blocks_str=str(st.f_bfree),
            avail_blocks=st.f_bavail,
            avail_blocks_str=str(st.f_bavail),
            files=st.f_files,
            free_files=st.f_ffree,
            name_max=st.f_namemax,
            fsid=str(st.f_fsid),
            total_bytes=st.f_blocks * st.f_frsize,
            total_bytes_str=str(st.f_blocks * st.f_frsize),
            free_bytes=st.f_bfree * st.f_frsize,
            free_bytes_str=str(st.f_bfree * st.f_frsize),
            avail_bytes=st.f_bavail * st.f_frsize,
            avail_bytes_str=str(st.f_bavail * st.f_frsize),
        )
