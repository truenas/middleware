import contextlib

from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def directory(path, options=None):
    call('filesystem.mkdir', {'path': path} | (options or {}))

    try:
        yield path
    finally:
        ssh(f'rm -rf {path}')
