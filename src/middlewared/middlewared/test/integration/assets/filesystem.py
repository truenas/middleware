import contextlib

from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def directory(path, options=None):
    call('filesystem.mkdir', {'path': path} | (options or {}))

    try:
        yield path
    finally:
        ssh(f'rm -rf {path}')


@contextlib.contextmanager
def file(path, size=None):
    """
    Create a simple file
    * path is the full-pathname. e.g. /mnt/tank/dataset/filename
    * If size is None then use 'touch',
      else create a random filled file of size bytes.
      Creation will be faster if size is a power of 2, e.g. 1024 or 1048576
    """
    try:
        if size is None:
            ssh(f"touch {path}")
        else:
            t = 1048576
            while t > 1 and size % t != 0:
                t = t // 2
            ssh(f"dd if=/dev/urandom of={path} bs={t} count={size // t}")
        yield path
    finally:
        ssh(f"rm -rf {path}")
