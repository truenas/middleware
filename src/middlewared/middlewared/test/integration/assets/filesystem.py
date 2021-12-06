import contextlib

from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def directory(path):
    call('filesystem.mkdir', path)

    try:
        yield path
    finally:
        ssh(f'rm -rf {path}')
