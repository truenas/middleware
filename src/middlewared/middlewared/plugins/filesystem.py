import binascii
import errno
import functools
import grp
import os
import pathlib
import pwd
import shutil
import stat as statlib
import time

import pyinotify

from middlewared.event import EventSource
from middlewared.plugins.pwenc import PWENC_FILE_SECRET
from middlewared.plugins.cluster_linux.utils import CTDBConfig, FuseConfig
from middlewared.plugins.filesystem_ import chflags, stat_x
from middlewared.schema import accepts, Bool, Dict, Float, Int, List, Ref, returns, Path, Str
from middlewared.service import private, CallError, filterable_returns, Service, job
from middlewared.utils import filter_list


class FilesystemService(Service):

    class Config:
        cli_namespace = 'storage.filesystem'

    @accepts(Str('path'))
    @returns(Bool())
    def is_immutable(self, path):
        """
        Retrieves boolean which is set when immutable flag is set on `path`.
        """
        return chflags.is_immutable_set(path)

    @accepts(Bool('set_flag'), Str('path'))
    @returns()
    def set_immutable(self, set_flag, path):
        """
        Set/Unset immutable flag at `path`.

        `set_flag` when set will set immutable flag and when unset will unset immutable flag at `path`.
        """
        chflags.set_immutable(path, set_flag)

    @private
    def resolve_cluster_path(self, path, ignore_ctdb=False):
        """
        Convert a "CLUSTER:"-prefixed path to an absolute path
        on the server.
        """
        if not path.startswith(FuseConfig.FUSE_PATH_SUBST.value):
            return path

        gluster_volume = path[8:].split("/")[0]
        if gluster_volume == CTDBConfig.CTDB_VOL_NAME.value and not ignore_ctdb:
            raise CallError('access to ctdb volume is not permitted.', errno.EPERM)
        elif not gluster_volume:
            raise CallError(f'More than the prefix "{FuseConfig.FUSE_PATH_SUBST.value}" must be provided')

        is_mounted = self.middleware.call_sync('gluster.fuse.is_mounted', {'name': gluster_volume})
        if not is_mounted:
            raise CallError(f'{gluster_volume}: cluster volume is not mounted.', errno.ENXIO)

        cluster_path = path.replace(FuseConfig.FUSE_PATH_SUBST.value, f'{FuseConfig.FUSE_PATH_BASE.value}/')
        return cluster_path

    @accepts(Str('path'))
    @returns(Ref('path_entry'))
    def mkdir(self, path):
        """
        Create a directory at the specified path.
        """
        path = self.resolve_cluster_path(path)
        is_clustered = path.startswith("/cluster")

        p = pathlib.Path(path)
        if not p.is_absolute():
            raise CallError(f'{path}: not an absolute path.', errno.EINVAL)

        if p.exists():
            raise CallError(f'{path}: path already exists.', errno.EEXIST)

        realpath = os.path.realpath(path)
        if not is_clustered and not realpath.startswith('/mnt/'):
            raise CallError(f'{path}: path not permitted', errno.EPERM)

        os.mkdir(path)
        stat = p.stat()
        data = {
            'name': p.parts[-1],
            'path': path,
            'realpath': realpath,
            'type': 'DIRECTORY',
            'size': stat.st_size,
            'mode': stat.st_mode,
            'acl': False if self.acl_is_trivial(path) else True,
            'uid': stat.st_uid,
            'gid': stat.st_gid,
        }

        return data

    @accepts(Str('path', required=True), Ref('query-filters'), Ref('query-options'))
    @filterable_returns(Dict(
        'path_entry',
        Str('name', required=True),
        Path('path', required=True),
        Path('realpath', required=True),
        Str('type', required=True, enum=['DIRECTORY', 'FILE', 'SYMLINK', 'OTHER']),
        Int('size', required=True, null=True),
        Int('mode', required=True, null=True),
        Bool('acl', required=True, null=True),
        Int('uid', required=True, null=True),
        Int('gid', required=True, null=True),
        register=True
    ))
    def listdir(self, path, filters, options):
        """
        Get the contents of a directory.

        Paths on clustered volumes may be specifed with the path prefix
        `CLUSTER:<volume name>`. For example, to list directories
        in the directory 'data' in the clustered volume `smb01`, the
        path should be specified as `CLUSTER:smb01/data`.

        Each entry of the list consists of:
          name(str): name of the file
          path(str): absolute path of the entry
          realpath(str): absolute real path of the entry (if SYMLINK)
          type(str): DIRECTORY | FILE | SYMLINK | OTHER
          size(int): size of the entry
          mode(int): file mode/permission
          uid(int): user id of entry owner
          gid(int): group id of entry onwer
          acl(bool): extended ACL is present on file
        """

        def stat_entry(entry):
            out = {'st': None, 'etype': None}
            try:
                out['st'] = entry.lstat()
            except Exception:
                return None

            if statlib.S_ISDIR(out['st'].st_mode):
                out['etype'] = 'DIRECTORY'

            elif statlib.S_ISLNK(out['st'].st_mode):
                out['etype'] = 'SYMLINK'
                try:
                    out['st'] = entry.stat()
                except Exception:
                    return None

            elif statlib.S_ISREG(out['st'].st_mode):
                out['etype'] = 'FILE'

            else:
                out['etype'] = 'OTHER'

            if dir_only and out['etype'] != 'DIRECTORY':
                return None

            elif file_only and out['etype'] != 'FILE':
                return None

            return out

        path = self.resolve_cluster_path(path)
        path = pathlib.Path(path)
        if not path.exists():
            raise CallError(f'Directory {path} does not exist', errno.ENOENT)

        if not path.is_dir():
            raise CallError(f'Path {path} is not a directory', errno.ENOTDIR)

        if 'ix-applications' in path.parts:
            raise CallError('Ix-applications is a system managed dataset and its contents cannot be listed')

        file_only = False
        dir_only = False
        for filter in filters:
            if filter[0] not in ['type']:
                continue

            if filter[1] != '=' and filter[2] not in ['DIRECTORY', 'FILE']:
                continue

            if filter[2] == 'DIRECTORY':
                dir_only = True
            else:
                file_only = True

        rv = []
        if dir_only and file_only:
            return rv

        only_top_level = path.absolute() == pathlib.Path('/mnt')
        for entry in path.iterdir():
            st = stat_entry(entry)
            if st is None:
                continue

            if only_top_level and not entry.is_mount():
                # sometimes (on failures) the top-level directory
                # where the zpool is mounted does not get removed
                # after the zpool is exported. WebUI calls this
                # specifying `/mnt` as the path. This is used when
                # configuring shares in the "Path" drop-down. To
                # prevent shares from being configured to point to
                # a path that doesn't exist on a zpool, we'll
                # filter these here.
                continue
            if 'ix-applications' in entry.parts:
                continue

            etype = st['etype']
            stat = st['st']
            realpath = entry.resolve().as_posix() if etype == 'SYMLINK' else entry.absolute().as_posix()

            data = {
                'name': entry.name,
                'path': entry.as_posix().replace(
                    f'{FuseConfig.FUSE_PATH_BASE.value}/', FuseConfig.FUSE_PATH_SUBST.value
                ),
                'realpath': realpath,
                'type': etype,
                'size': stat.st_size,
                'mode': stat.st_mode,
                'acl': False if self.acl_is_trivial(realpath) else True,
                'uid': stat.st_uid,
                'gid': stat.st_gid,
            }

            rv.append(data)

        return filter_list(rv, filters=filters or [], options=options or {})

    @accepts(Str('path'))
    @returns(Dict(
        'path_stats',
        Int('size', required=True),
        Int('mode', required=True),
        Int('uid', required=True),
        Int('gid', required=True),
        Float('atime', required=True),
        Float('mtime', required=True),
        Float('ctime', required=True),
        Int('dev', required=True),
        Int('inode', required=True),
        Int('nlink', required=True),
        Str('user', null=True, required=True),
        Str('group', null=True, required=True),
        Bool('acl', required=True),
    ))
    def stat(self, path):
        """
        Return the filesystem stat(2) for a given `path`.

        Paths on clustered volumes may be specifed with the path prefix
        `CLUSTER:<volume name>`. For example, to list directories
        in the directory 'data' in the clustered volume `smb01`, the
        path should be specified as `CLUSTER:smb01/data`.
        """
        path = self.resolve_cluster_path(path)
        try:
            stat = os.stat(path, follow_symlinks=False)
        except FileNotFoundError:
            raise CallError(f'Path {path} not found', errno.ENOENT)

        stat = {
            'size': stat.st_size,
            'mode': stat.st_mode,
            'uid': stat.st_uid,
            'gid': stat.st_gid,
            'atime': stat.st_atime,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime,
            'dev': stat.st_dev,
            'inode': stat.st_ino,
            'nlink': stat.st_nlink,
        }

        try:
            stat['user'] = pwd.getpwuid(stat['uid']).pw_name
        except KeyError:
            stat['user'] = None

        try:
            stat['group'] = grp.getgrgid(stat['gid']).gr_name
        except KeyError:
            stat['group'] = None

        stat['acl'] = False if self.acl_is_trivial(path) else True

        return stat

    @private
    @accepts(
        Str('path'),
        Str('content', max_length=2048000),
        Dict(
            'options',
            Bool('append', default=False),
            Int('mode'),
        ),
    )
    def file_receive(self, path, content, options):
        """
        Simplified file receiving method for small files.

        `content` must be a base 64 encoded file content.
        """
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        if options.get('append'):
            openmode = 'ab'
        else:
            openmode = 'wb+'
        with open(path, openmode) as f:
            f.write(binascii.a2b_base64(content))
        mode = options.get('mode')
        if mode:
            os.chmod(path, mode)
        if path == PWENC_FILE_SECRET:
            self.middleware.call_sync('pwenc.reset_secret_cache')
        return True

    @private
    @accepts(
        Str('path'),
        Dict(
            'options',
            Int('offset'),
            Int('maxlen'),
        ),
    )
    def file_get_contents(self, path, options):
        """
        Get contents of a file `path` in base64 encode.

        DISCLAIMER: DO NOT USE THIS FOR BIG FILES (> 500KB).
        """
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            if options.get('offset'):
                f.seek(options['offset'])
            data = binascii.b2a_base64(f.read(options.get('maxlen'))).decode().strip()
        return data

    @accepts(Str('path'))
    @returns()
    @job(pipes=["output"])
    async def get(self, job, path):
        """
        Job to get contents of `path`.
        """

        if not os.path.isfile(path):
            raise CallError(f'{path} is not a file')

        with open(path, 'rb') as f:
            await self.middleware.run_in_thread(shutil.copyfileobj, f, job.pipes.output.w)

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
    async def put(self, job, path, options):
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

        with open(path, openmode) as f:
            await self.middleware.run_in_thread(shutil.copyfileobj, job.pipes.input.r, f)

        mode = options.get('mode')
        if mode:
            os.chmod(path, mode)
        return True

    @accepts(Str('path'))
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
        Int('files', required=True),
        Int('free_files', required=True),
        Int('name_max', required=True),
        Int('total_bytes', required=True),
        Int('free_bytes', required=True),
        Int('avail_bytes', required=True),
    ))
    def statfs(self, path):
        """
        Return stats from the filesystem of a given path.

        Paths on clustered volumes may be specifed with the path prefix
        `CLUSTER:<volume name>`. For example, to list directories
        in the directory 'data' in the clustered volume `smb01`, the
        path should be specified as `CLUSTER:smb01/data`.

        Raises:
            CallError(ENOENT) - Path not found
        """
        # check to see if this is a clustered path and if it is
        # resolve it to an absolute path
        # NOTE: this converts path prefixed with 'CLUSTER:' to '/cluster/...'
        path = self.resolve_cluster_path(path, ignore_ctdb=True)

        allowed_prefixes = ('/mnt/', FuseConfig.FUSE_PATH_BASE.value)
        if not path.startswith(allowed_prefixes):
            # if path doesn't start with '/mnt/' bail early
            raise CallError(f'Path must start with {" or ".join(allowed_prefixes)}')
        elif path == '/mnt/':
            # means the path given to us was a literal '/mnt/' which is incorrect.
            # NOTE: if the user provided 'CLUSTER:' as the literal path then
            # self.resolve_cluster_path() will raise a similar error
            raise CallError('Path must include more than "/mnt/"')

        try:
            st = os.statvfs(path)
        except FileNotFoundError:
            raise CallError('Path not found.', errno.ENOENT)

        # get the closest mountpoint to the path provided
        mountpoint = pathlib.Path(path)
        while not mountpoint.is_mount():
            mountpoint = mountpoint.parent.absolute()

        # strip the `/mnt/` or `/cluster/` prefix from the mountpoint
        device = mountpoint.as_posix().removeprefix('/mnt/')
        device = device.removeprefix('/cluster/')

        # get fstype for given path based on major:minor entry in mountinfo
        stx = stat_x.statx(path)
        maj_min = f'{stx.stx_dev_major}:{stx.stx_dev_minor}'
        fstype = None
        with open('/proc/self/mountinfo') as f:
            # example lines look like this. We use `find()` to keep the `.split()` calls to only 2 (instead of 3)
            # (minor optimization, but still one nonetheless)
            # "26 1 0:23 / / rw,relatime shared:1 - zfs boot-pool/ROOT/22.02-MASTER-20211129-015838 rw,xattr,posixacl"
            # OR
            # "129 26 0:50 / /mnt/data rw,noatime shared:72 - zfs data rw,xattr,posixacl"
            for line in f:
                if line.find(maj_min) != -1:
                    fstype = line.rsplit(' - ')[1].split()[0]
                    break

        return {
            'flags': [],
            'fstype': fstype,
            'source': device,
            'dest': mountpoint.as_posix(),
            'blocksize': st.f_frsize,
            'total_blocks': st.f_blocks,
            'free_blocks': st.f_bfree,
            'avail_blocks': st.f_bavail,
            'files': st.f_files,
            'free_files': st.f_ffree,
            'name_max': st.f_namemax,
            'fsid': [],
            'total_bytes': st.f_blocks * st.f_frsize,
            'free_bytes': st.f_bfree * st.f_frsize,
            'avail_bytes': st.f_bavail * st.f_frsize,
        }

    @accepts(Str('path'))
    @returns(Bool('paths_acl_is_trivial'))
    def acl_is_trivial(self, path):
        """
        Returns True if the ACL can be fully expressed as a file mode without losing
        any access rules.

        Paths on clustered volumes may be specifed with the path prefix
        `CLUSTER:<volume name>`. For example, to list directories
        in the directory 'data' in the clustered volume `smb01`, the
        path should be specified as `CLUSTER:smb01/data`.
        """
        path = self.resolve_cluster_path(path)
        if not os.path.exists(path):
            raise CallError(f'Path not found [{path}].', errno.ENOENT)

        acl = self.middleware.call_sync('filesystem.getacl', path, True)
        return acl['trivial']


class FileFollowTailEventSource(EventSource):

    """
    Retrieve last `no_of_lines` specified as an integer argument for a specific `path` and then
    any new lines as they are added. Specified argument has the format `path:no_of_lines` ( `/var/log/messages:3` ).

    `no_of_lines` is optional and if it is not specified it defaults to `3`.

    However `path` is required for this.
    """

    def run_sync(self):
        if ':' in self.arg:
            path, lines = self.arg.rsplit(':', 1)
            lines = int(lines)
        else:
            path = self.arg
            lines = 3
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
