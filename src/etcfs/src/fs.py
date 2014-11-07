__author__ = 'jceel'

import os
import errno
import time
from fuse import FuseOSError, Operations
from cStringIO import StringIO

class FileCache(object):
    class CacheItem(object):
        def __init__(self, data=None):
            self.mtime = time.time()
            self.data = StringIO(data)

    def __init__(self):
        self.items = {}

    def exists(self, filename):
        return filename in self.items.keys()

    def put(self, filename, data, immutable=False):
        self.items[filename] = self.CacheItem(data)

    def get(self, filename):
        if not self.exists(filename):
            return None

        item = self.items[filename]
        return item.data

    def read(self, filename, offset, length):
        if not self.exists(filename):
            return None

        item = self.items[filename]
        item.data.seek(offset)
        return item.data.read(length)

    def is_actual(self, filename, mtime):
        pass

class EtcFS(Operations):
    def __init__(self, ctx, root):
        self.context = ctx
        self.root = root
        self.cache = FileCache()

    def __full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def __is_managed(self, path):
        return path in self.context.managed_files.keys()

    def access(self, path, mode):
        print 'access %s' % path
        if self.__is_managed(path):
            return True
        else:
            return os.access(self.__full_path(path), mode)

    def chmod(self, path, mode):
        raise FuseOSError(errno.EACCES)

    def chown(self, path, uid, gid):
        raise FuseOSError(errno.EACCES)

    def getattr(self, path, fh=None):
        print 'getattr %s' % path
        if self.__is_managed(path[1:]):
            full_path = self.context.managed_files[path[1:]]
            contents = self.context.generate_file(full_path)
            size = len(contents)
            self.cache.put(path, contents)
        else:
            full_path = self.__full_path(path)
            size = os.path.getsize(full_path)

        print 'full path %s' % full_path
        st = os.lstat(full_path)
        return {
            'st_atime': time.time(),
            'st_ctime': time.time(),
            'st_gid': st.st_gid,
            'st_mode': st.st_mode,
            'st_mtime': time.time(),
            'st_nlink': 0,
            'st_size': size,
            'st_uid': st.st_uid
        }

    def readdir(self, path, fh):
        full_path = self.__full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r
        for r in filter(lambda x: x.startswith(path), self.context.managed_files):
            yield os.path.basename(r)

    def readlink(self, path):
        print 'readlink %s' % path
        pathname = os.readlink(self.__full_path(path))
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
        print 'statfs %s' % path
        full_path = self.__full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        raise FuseOSError(errno.EACCES)

    def symlink(self, target, name):
        return os.symlink(self.__full_path(target), self.__full_path(name))

    def rename(self, old, new):
        raise FuseOSError(errno.EACCES)

    def link(self, target, name):
        raise FuseOSError(errno.EACCES)

    def utimens(self, path, times=None):
        return os.utime(self.__full_path(path), times)

    def open(self, path, flags):
        print 'attempting to open %s' % path
        if self.__is_managed(path[1:]):
            return 1
        else:
            fp = self.__full_path(path)
            fo = open(fp, 'r')
            item = self.cache.put(path, fo.read())
            fo.close()
            return os.open(fp, flags)

    def create(self, path, mode, fi=None):
        return self.cache.put(path, None)

    def read(self, path, length, offset, fh):
        if self.__is_managed(path[1:]):
            return self.cache.read(path, offset, length)
        else:
            return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        if self.__is_managed(path[1:]):
            raise FuseOSError(errno.EACCES)

        fh.update(buf, offset)

    def truncate(self, path, length, fh=None):
        if self.__is_managed(path[1:]):
            raise FuseOSError(errno.EACCES)

        full_path = self.__full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        pass

    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)