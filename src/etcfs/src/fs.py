__author__ = 'jceel'

import os
import errno
import time
from fuse import FuseOSError, Operations

class FileCache(object):
    class CacheItem(object):
        def __init__(self):
            self.mtime = time.time()
            self.data = None

    def __init__(self):
        self.items = {}

    def exists(self, filename):
        pass

    def put(self, filename, data, immutable=False):
        pass

    def get(self, filename):
        pass

    def is_actual(self, filename, mtime):
        pass

class EtcFS(Operations):
    def __init__(self, root):
        self.root = root
        self.cache = FileCache()

    def __full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def __is_managed(self, path):
        pass

    def access(self, path, mode):
        if self.is_managed(path):
            return True
        else:
            return os.access(self._full_path(path), mode)

    def chmod(self, path, mode):
        raise FuseOSError(errno.EACCES)

    def chown(self, path, uid, gid):
        raise FuseOSError(errno.EACCES)

    def getattr(self, path, fh=None):
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        raise FuseOSError(errno.EACCES)

    def rmdir(self, path):
        raise FuseOSError(errno.EACCES)

    def mkdir(self, path, mode):
        raise FuseOSError(errno.EACCES)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        raise FuseOSError(errno.EACCES)

    def symlink(self, target, name):
        return os.symlink(self._full_path(target), self._full_path(name))

    def rename(self, old, new):
        raise FuseOSError(errno.EACCES)

    def link(self, target, name):
        raise FuseOSError(errno.EACCES)

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    def open(self, path, flags):
        if self.__is_managed(path):
            pass
        else:
            fp = self.__full_path(path)
            fo = open(fp, 'r')
            item = self.cache.put(path, fo.readall())
            fo.close()
            return item

    def create(self, path, mode, fi=None):
        return self.cache.put(path, None)

    def read(self, path, length, offset, fh):
        if self.__is_managed(path):
            pass
        else:
            return fh.read(length, offset)

    def write(self, path, buf, offset, fh):
        if self.__is_managed(path):
            raise FuseOSError(errno.EACCES)

        fh.update(buf, offset)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        pass

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)