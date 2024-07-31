import binascii
import errno
import functools
import os
import pathlib
import shutil
import stat as statlib
import time

import pyinotify

from itertools import product
from middlewared.event import EventSource
from middlewared.plugins.pwenc import PWENC_FILE_SECRET, PWENC_FILE_SECRET_MODE
from middlewared.plugins.docker.state_utils import IX_APPS_DIR_NAME
from middlewared.plugins.filesystem_ import chflags
from middlewared.schema import accepts, Bool, Dict, Float, Int, List, Ref, returns, Path, Str, UnixPerm
from middlewared.service import private, CallError, filterable_returns, filterable, Service, job
from middlewared.utils import filter_list
from middlewared.utils.filesystem import attrs, stat_x
from middlewared.utils.filesystem.acl import acl_is_present
from middlewared.utils.filesystem.constants import FileType
from middlewared.utils.filesystem.directory import DirectoryIterator
from middlewared.utils.filesystem.utils import timespec_convert
from middlewared.utils.mount import getmntinfo
from middlewared.utils.nss import pwd, grp
from middlewared.utils.path import FSLocation, path_location, is_child_realpath


class FilesystemService(Service):

    class Config:
        cli_private = True

    @accepts(Str('path'), roles=['FILESYSTEM_ATTRS_READ'])
    @returns(Bool())
    def is_immutable(self, path):
        """
        Retrieves boolean which is set when immutable flag is set on `path`.
        """
        stx_attrs = self.stat(path)['attributes']
        return 'IMMUTABLE' in stx_attrs

    @accepts(Bool('set_flag'), Str('path'), roles=['FILESYSTEM_ATTRS_WRITE'])
    @returns()
    def set_immutable(self, set_flag, path):
        """
        Set/Unset immutable flag at `path`.

        `set_flag` when set will set immutable flag and when unset will unset immutable flag at `path`.
        """
        chflags.set_immutable(path, set_flag)

    @accepts(Dict(
        'set_zfs_file_attributes',
        Path('path', required=True),
        Dict(
            'zfs_file_attributes',
            Bool('readonly'),
            Bool('hidden'),
            Bool('system'),
            Bool('archive'),
            Bool('immutable'),
            Bool('nounlink'),
            Bool('appendonly'),
            Bool('offline'),
            Bool('sparse'),
            register=True
        ),
    ), roles=['FILESYSTEM_ATTRS_WRITE'])
    @returns()
    def set_zfs_attributes(self, data):
        """
        Set special ZFS-related file flags on the specified path

        `readonly` - this maps to READONLY MS-DOS attribute. When set, file may not be
        written to (toggling does not impact existing file opens).

        `hidden` - this maps to HIDDEN MS-DOS attribute. When set, the SMB HIDDEN flag
        is set and file is "hidden" from the perspective of SMB clients.

        `system` - this maps to SYSTEM MS-DOS attribute. Is presented to SMB clients, but
        has no impact on local filesystem.

        `archive` - this maps to ARCHIVE MS-DOS attribute. Value is reset to True whenever
        file is modified.

        `immutable` - file may not be altered or deleted. Also appears as IMMUTABLE in
        attributes in `filesystem.stat` output and as STATX_ATTR_IMMUTABLE in statx() response.

        `nounlink` - file may be altered but not deleted.

        `appendonly` - file may only be opened with O_APPEND flag. Also appears as APPEND in
        attributes in `filesystem.stat` output and as STATX_ATTR_APPEND in statx() response.

        `offline` - this maps to OFFLINE MS-DOS attribute. Is presented to SMB clients, but
        has no impact on local filesystem.

        `sparse` - maps to SPARSE MS-DOS attribute. Is presented to SMB clients, but has
        no impact on local filesystem.
        """
        return attrs.set_zfs_file_attributes_dict(data['path'], data['zfs_file_attributes'])

    @accepts(Str('path'), roles=['FILESYSTEM_ATTRS_READ'])
    @returns(Ref('zfs_file_attributes'))
    def get_zfs_attributes(self, path):
        """
        Get the current ZFS attributes for the file at the given path
        """
        fd = os.open(path, os.O_RDONLY)
        try:
            attr_mask = attrs.fget_zfs_file_attributes(fd)
        finally:
            os.close(fd)

        return attrs.zfs_attributes_to_dict(attr_mask)

    @private
    def is_child(self, child, parent):
        for to_check in product(
            child if isinstance(child, list) else [child],
            parent if isinstance(parent, list) else [parent]
        ):
            if is_child_realpath(to_check[0], to_check[1]):
                return True

        return False

    @private
    def is_dataset_path(self, path):
        return path.startswith('/mnt/') and os.stat(path).st_dev != os.stat('/mnt').st_dev

    @private
    @filterable
    def mount_info(self, filters, options):
        mntinfo = getmntinfo()
        return filter_list(list(mntinfo.values()), filters, options)

    @accepts(Dict(
        'filesystem_mkdir',
        Str('path'),
        Dict(
            'options',
            UnixPerm('mode', default='755'),
            Bool('raise_chmod_error', default=True)
        ),
    ), deprecated=[(
        lambda args: len(args) == 1 and isinstance(args[0], str),
        lambda mkdir_path: [{
            'path': mkdir_path
        }]
    )], roles=['FILESYSTEM_DATA_WRITE'])
    @returns(Ref('path_entry'))
    def mkdir(self, data):
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
        path = data['path']
        options = data['options']
        mode = int(options['mode'], 8)

        p = pathlib.Path(path)
        if not p.is_absolute():
            raise CallError(f'{path}: not an absolute path.', errno.EINVAL)

        if p.exists():
            raise CallError(f'{path}: path already exists.', errno.EEXIST)

        realpath = os.path.realpath(path)
        if not realpath.startswith(('/mnt/', '/root/.ssh', '/home/admin/.ssh', '/home/truenas_admin/.ssh')):
            raise CallError(f'{path}: path not permitted', errno.EPERM)

        os.mkdir(path, mode=mode)
        stat = p.stat()
        if statlib.S_IMODE(stat.st_mode) != mode:
            # This may happen if requested mode is greater than umask
            # or if underlying dataset has restricted aclmode and ACL is present
            try:
                os.chmod(path, mode)
            except Exception:
                if options['raise_chmod_error']:
                    os.rmdir(path)
                    raise

                self.logger.debug(
                    '%s: failed to set mode %s on path after mkdir call',
                    path, options['mode'], exc_info=True
                )

        return {
            'name': p.parts[-1],
            'path': path,
            'realpath': realpath,
            'type': 'DIRECTORY',
            'size': stat.st_size,
            'mode': stat.st_mode,
            'acl': False if self.acl_is_trivial(path) else True,
            'uid': stat.st_uid,
            'gid': stat.st_gid,
            'is_mountpoint': False,
            'is_ctldir': False,
            'xattrs': [],
            'zfs_attrs': ['ARCHIVE']
        }

    @accepts(
        Str('path', required=True),
        Ref('query-filters'),
        Ref('query-options'),
        roles=['FILESYSTEM_ATTRS_READ']
    )
    @filterable_returns(Dict(
        'path_entry',
        Str('name', required=True),
        Path('path', required=True),
        Path('realpath', required=True),
        Str('type', required=True, enum=['DIRECTORY', 'FILE', 'SYMLINK', 'OTHER']),
        Int('size', required=True, null=True),
        Int('allocation_size', required=True, null=True),
        Int('mode', required=True, null=True),
        Int('mount_id', required=True, null=True),
        Bool('acl', required=True, null=True),
        Int('uid', required=True, null=True),
        Int('gid', required=True, null=True),
        Bool('is_mountpoint', required=True),
        Bool('is_ctldir', required=True),
        List(
            'attributes',
            required=True,
            items=[Str('statx_attribute', enum=[attr.name for attr in stat_x.StatxAttr])]
        ),
        List('xattrs', required=True, null=True),
        List('zfs_attrs', required=True, null=True),
        register=True
    ))
    def listdir(self, path, filters, options):
        """
        Get the contents of a directory.

        Each entry of the list consists of:
          name(str): name of the file
          path(str): absolute path of the entry
          realpath(str): absolute real path of the entry (if SYMLINK)
          type(str): DIRECTORY | FILE | SYMLINK | OTHER
          size(int): size of the entry
          allocation_size(int): on-disk size of entry
          mode(int): file mode/permission
          uid(int): user id of entry owner
          gid(int): group id of entry owner
          acl(bool): extended ACL is present on file
          is_mountpoint(bool): path is a mountpoint
          is_ctldir(bool): path is within special .zfs directory
          attributes(list): list of statx file attributes that apply to the
          file. See statx(2) manpage for more details.
          xattrs(list): list of extended attribute names.
          zfs_attrs(list): list of ZFS file attributes on file
        """

        path = pathlib.Path(path)
        if not path.exists():
            raise CallError(f'Directory {path} does not exist', errno.ENOENT)

        if not path.is_dir():
            raise CallError(f'Path {path} is not a directory', errno.ENOTDIR)

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

        if path.absolute() == pathlib.Path('/mnt'):
            # sometimes (on failures) the top-level directory
            # where the zpool is mounted does not get removed
            # after the zpool is exported. WebUI calls this
            # specifying `/mnt` as the path. This is used when
            # configuring shares in the "Path" drop-down. To
            # prevent shares from being configured to point to
            # a path that doesn't exist on a zpool, we'll
            # filter these here.
            filters.extend([['is_mountpoint', '=', True], ['name', '!=', IX_APPS_DIR_NAME]])

        with DirectoryIterator(path, file_type=file_type) as d_iter:
            return filter_list(d_iter, filters, options)

    @accepts(Str('path'), roles=['FILESYSTEM_ATTRS_READ'])
    @returns(Dict(
        'path_stats',
        Str('realpath', required=True),
        Int('size', required=True),
        Int('allocation_size', required=True),
        Int('mode', required=True),
        Int('uid', required=True),
        Int('gid', required=True),
        Float('atime', required=True),
        Float('mtime', required=True),
        Float('ctime', required=True),
        Float('btime', required=True),
        Int('dev', required=True),
        Int('mount_id', required=True),
        Int('inode', required=True),
        Int('nlink', required=True),
        Bool('is_mountpoint', required=True),
        Bool('is_ctldir', required=True),
        List(
            'attributes',
            required=True,
            items=[Str('statx_attribute', enum=[attr.name for attr in stat_x.StatxAttr])]
        ),
        Str('user', null=True, required=True),
        Str('group', null=True, required=True),
        Bool('acl', required=True),
    ))
    def stat(self, _path):
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

        st = stat_x.statx_entry_impl(path, None)
        if st is None:
            raise CallError(f'Path {_path} not found', errno.ENOENT)

        realpath = path.resolve().as_posix() if st['etype'] == 'SYMLINK' else path.absolute().as_posix()

        stat = {
            'realpath': realpath,
            'type': st['etype'],
            'size': st['st'].stx_size,
            'allocation_size': st['st'].stx_blocks * 512,
            'mode': st['st'].stx_mode,
            'uid': st['st'].stx_uid,
            'gid': st['st'].stx_gid,
            'atime': timespec_convert(st['st'].stx_atime),
            'mtime': timespec_convert(st['st'].stx_mtime),
            'ctime': timespec_convert(st['st'].stx_ctime),
            'btime': timespec_convert(st['st'].stx_btime),
            'mount_id': st['st'].stx_mnt_id,
            'dev': os.makedev(st['st'].stx_dev_major, st['st'].stx_dev_minor),
            'inode': st['st'].stx_ino,
            'nlink': st['st'].stx_nlink,
            'is_mountpoint': 'MOUNT_ROOT' in st['attributes'],
            'is_ctldir': st['is_ctldir'],
            'attributes': st['attributes']
        }

        try:
            stat['user'] = pwd.getpwuid(stat['uid']).pw_name
        except KeyError:
            stat['user'] = None

        try:
            stat['group'] = grp.getgrgid(stat['gid']).gr_name
        except KeyError:
            stat['group'] = None

        stat['acl'] = False if self.acl_is_trivial(_path) else True

        return stat

    @private
    @accepts(
        Str('path'),
        Str('content', max_length=2048000),
        Dict(
            'options',
            Bool('append', default=False),
            Int('mode'),
            Int('uid'),
            Int('gid'),
        ),
    )
    def file_receive(self, path, content, options):
        """
        Simplified file receiving method for small files.

        `content` must be a base 64 encoded file content.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'ab' if options.get('append') else 'wb+') as f:
            f.write(binascii.a2b_base64(content))
            if path == PWENC_FILE_SECRET:
                # don't allow someone to clobber mode/ownership
                os.fchmod(f.fileno(), PWENC_FILE_SECRET_MODE)
                os.fchown(f.fileno(), 0, 0)
            else:
                if mode := options.get('mode'):
                    os.fchmod(f.fileno(), mode)
                # -1 means don't change uid/gid if the one provided is
                # the same that is on disk already
                os.fchown(f.fileno(), options.get('uid', -1), options.get('gid', -1))

        if path == PWENC_FILE_SECRET:
            self.middleware.call_sync('pwenc.reset_secret_cache')

        return True

    @accepts(Str('path'))
    @returns()
    @job(pipes=["output"])
    def get(self, job, path):
        """
        Job to get contents of `path`.
        """

        if not os.path.isfile(path):
            raise CallError(f'{path} is not a file')

        with open(path, 'rb') as f:
            shutil.copyfileobj(f, job.pipes.output.w)

    @accepts(
        Str('path'),
        Dict(
            'options',
            Bool('append', default=False),
            Int('mode'),
        ),
    )
    @returns(Bool('successful_put'))
    @job(pipes=["input"])
    def put(self, job, path, options):
        """
        Job to put contents to `path`.
        """
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        if options.get('append'):
            openmode = 'ab'
        else:
            openmode = 'wb+'

        try:
            with open(path, openmode) as f:
                shutil.copyfileobj(job.pipes.input.r, f)
        except PermissionError:
            raise CallError(f'Unable to put contents at {path!r} as the path exists on a locked dataset', errno.EINVAL)

        mode = options.get('mode')
        if mode:
            os.chmod(path, mode)
        return True

    @accepts(Str('path'), roles=['FILESYSTEM_ATTRS_READ'])
    @returns(Dict(
        'path_statfs',
        List('flags', required=True),
        List('fsid', required=True),
        Str('fstype', required=True),
        Str('source', required=True),
        Str('dest', required=True),
        Int('blocksize', required=True),
        Int('total_blocks', required=True),
        Int('free_blocks', required=True),
        Int('avail_blocks', required=True),
        Str('total_blocks_str', required=True),
        Str('free_blocks_str', required=True),
        Str('avail_blocks_str', required=True),
        Int('files', required=True),
        Int('free_files', required=True),
        Int('name_max', required=True),
        Int('total_bytes', required=True),
        Int('free_bytes', required=True),
        Int('avail_bytes', required=True),
        Str('total_bytes_str', required=True),
        Str('free_bytes_str', required=True),
        Str('avail_bytes_str', required=True),
    ))
    def statfs(self, path):
        """
        Return stats from the filesystem of a given path.

        Raises:
            CallError(ENOENT) - Path not found
        """
        if not path.startswith('/mnt/'):
            raise CallError('Path must start with "/mnt/"')
        elif path == '/mnt/':
            raise CallError('Path must include more than "/mnt/"')

        try:
            fd = os.open(path, os.O_PATH)
            try:
                st = os.fstatvfs(fd)
                mntid = stat_x.statx('', dir_fd=fd, flags=stat_x.ATFlags.EMPTY_PATH.value).stx_mnt_id
            finally:
                os.close(fd)

        except FileNotFoundError:
            raise CallError('Path not found.', errno.ENOENT)

        mntinfo = getmntinfo(mnt_id=mntid)[mntid]
        flags = mntinfo['mount_opts']
        for flag in mntinfo['super_opts']:
            if flag in flags:
                continue
            flags.append(flag)

        result = {
            'flags': flags,
            'fstype': mntinfo['fs_type'].lower(),
            'source': mntinfo['mount_source'],
            'dest': mntinfo['mountpoint'],
            'blocksize': st.f_frsize,
            'total_blocks': st.f_blocks,
            'free_blocks': st.f_bfree,
            'avail_blocks': st.f_bavail,
            'files': st.f_files,
            'free_files': st.f_ffree,
            'name_max': st.f_namemax,
            'fsid': [str(st.f_fsid)],
            'total_bytes': st.f_blocks * st.f_frsize,
            'free_bytes': st.f_bfree * st.f_frsize,
            'avail_bytes': st.f_bavail * st.f_frsize,
        }
        for k in ['total_blocks', 'free_blocks', 'avail_blocks', 'total_bytes', 'free_bytes', 'avail_bytes']:
            result[f'{k}_str'] = str(result[k])
        return result

    @accepts(Str('path'), roles=['FILESYSTEM_ATTRS_READ'])
    @returns(Bool('paths_acl_is_trivial'))
    def acl_is_trivial(self, path):
        """
        Returns True if the ACL can be fully expressed as a file mode without losing
        any access rules.
        """
        if not os.path.exists(path):
            raise CallError(f'Path not found [{path}].', errno.ENOENT)

        return not acl_is_present(os.listxattr(path))


class FileFollowTailEventSource(EventSource):
    """
    Retrieve last `no_of_lines` specified as an integer argument for a specific `path` and then
    any new lines as they are added. Specified argument has the format `path:no_of_lines` ( `/var/log/messages:3` ).

    `no_of_lines` is optional and if it is not specified it defaults to `3`.

    However, `path` is required for this.
    """

    def parse_arg(self):
        if ':' in self.arg:
            path, lines = self.arg.rsplit(':', 1)
            lines = int(lines)
        else:
            path = self.arg
            lines = 3

        return path, lines

    def run_sync(self):
        path, lines = self.parse_arg()

        if not os.path.exists(path):
            # FIXME: Error?
            return

        bufsize = 8192
        fsize = os.stat(path).st_size
        if fsize < bufsize:
            bufsize = fsize
        i = 0
        with open(path, encoding='utf-8', errors='ignore') as f:
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

            for data in self._follow_path(path, f):
                self.send_event('ADDED', fields={'data': data})

    def _follow_path(self, path, f):
        queue = []
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

    def _follow_callback(self, queue, f, event):
        data = f.read()
        if data:
            queue.append(data)


def setup(middleware):
    middleware.register_event_source('filesystem.file_tail_follow', FileFollowTailEventSource)
