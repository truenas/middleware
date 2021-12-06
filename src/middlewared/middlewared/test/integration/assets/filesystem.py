import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def directory(path):
    call('filesystem.mkdir', path)

    try:
        yield path
    finally:
        call('filesystem.remove_directory', path)
