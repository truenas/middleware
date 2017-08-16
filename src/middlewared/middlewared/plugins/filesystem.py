from middlewared.schema import Bool, Dict, Int, Ref, Str, accepts
from middlewared.service import private, CallError, Service
from middlewared.utils import filter_list

import binascii
import errno
import os

import libzfs


class FilesystemService(Service):

    @accepts(Str('path'), Ref('query-filters'), Ref('query-options'))
    def listdir(self, path, filters=None, options=None):
        """
        Get the contents of a directory.

        Each entry of the list consists of:
          name(str): name of the file
          path(str): absolute path of the entry
          realpath(str): absolute real path of the entry (if SYMLINK)
          type(str): DIRECTORY | FILESYSTEM | SYMLINK | OTHER
          size(int): size of the entry
          mode(int): file mode/permission
          uid(int): user id of entry owner
          gid(int): group id of entry onwer
        """
        if not os.path.exists(path):
            raise CallError(f'Directory {path} does not exist', errno.ENOENT)

        if not os.path.isdir(path):
            raise CallError(f'Path {path} is not a directory', errno.ENOTDIR)

        rv = []
        for entry in os.scandir(path):
            if entry.is_dir():
                etype = 'DIRECTORY'
            elif entry.is_file():
                etype = 'FILE'
            elif entry.is_symlink():
                etype = 'SYMLINK'
            else:
                etype = 'OTHER'

            data = {
                'name': entry.name,
                'path': entry.path,
                'realpath': os.path.realpath(entry.path) if etype == 'SYMLINK' else entry.path,
                'type': etype,
            }
            try:
                stat = entry.stat()
                data.update({
                    'size': stat.st_size,
                    'mode': stat.st_mode,
                    'uid': stat.st_uid,
                    'gid': stat.st_gid,
                })
            except FileNotFoundError:
                data.update({'size': None, 'mode': None, 'uid': None, 'gid': None})
            rv.append(data)
        return filter_list(rv, filters=filters or [], options=options or {})

    @accepts(Str('path'))
    def stat(self, path):
        """
        Return the filesystem stat(2) for a given `path`.
        """
        try:
            stat = os.stat(path, follow_symlinks=False)
        except FileNotFoundError:
            raise CallError(f'Path {path} not found', errno.ENOENT)
        return {
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

    @private
    @accepts(
        Str('path'),
        Str('content'),
        Dict(
            'options',
            Bool('append', default=False),
            Int('mode'),
        ),
    )
    def file_receive(self, path, content, options=None):
        """
        Simplified file receiving method for small files.

        `content` must be a base 64 encoded file content.

        DISCLAIMER: DO NOT USE THIS FOR BIG FILES (> 500KB).
        """
        options = options or {}
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
    def file_get_contents(self, path, options=None):
        """
        Get contents of a file `path` in base64 encode.

        DISCLAIMER: DO NOT USE THIS FOR BIG FILES (> 500KB).
        """
        options = options or {}
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            if options.get('offset'):
                f.seek(options['offset'])
            data = binascii.b2a_base64(f.read(options.get('maxlen'))).decode().strip()
        return data

    @accepts(
        Str('dataset'),
        Str('name'),
        Bool('recursive'),
        Int('vmsnaps_count')
    )
    def zfs_mksnap(self, dataset, name, recursive=False, vmsnaps_count=0):
        """
        Take a snapshot from a given dataset.

        Returns:
            bool: True if succeed otherwise False.
        """
        zfs = libzfs.ZFS()

        try:
            ds = zfs.get_dataset(dataset)
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

        try:
            if recursive:
                ds.snapshots_recursive('{0}@{1}'.format(dataset, name))
            else:
                ds.snapshot('{0}@{1}'.format(dataset, name))

            if vmsnaps_count > 0:
                ds.properties['freenas:vmsynced'] = libzfs.ZFSUserProperty('Y')

            self.logger.info("Snapshot taken: {0}@{1}".format(dataset, name))
            return True
        except libzfs.ZFSException as err:
                self.logger.error("{0}".format(err))
                return False

    @accepts(
        Str('dataset'),
        Str('snap_name')
    )
    def zfs_rmsnap(self, dataset, snap_name):
        """
        Remove a snapshot from a given dataset.

        Returns:
            bool: True if succeed otherwise False.
        """
        zfs = libzfs.ZFS()

        try:
            ds = zfs.get_dataset(dataset)
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

        __snap_name = dataset + '@' + snap_name
        try:
            for snap in list(ds.snapshots):
                if snap.name == __snap_name:
                    ds.destroy_snapshot(snap_name)
                    self.logger.info("Destroyed snapshot: {0}".format(__snap_name))
                    return True
            self.logger.error("There is no snapshot {0} on dataset {1}".format(snap_name, dataset))
            return False
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

    @accepts(
        Str('snapshot'),
        Str('dataset_dst')
    )
    def zfs_clone(self, snapshot, dataset_dst):
        """
        Clone a given snapshot to a new dataset.

        Returns:
            bool: True if succeed otherwise False.
        """
        zfs = libzfs.ZFS()

        try:
            snp = zfs.get_snapshot(snapshot)
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False

        try:
            snp.clone(dataset_dst)
            self.logger.info("Cloned snapshot {0} to dataset {1}".format(snapshot, dataset_dst))
            return True
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            return False
