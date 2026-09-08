import contextlib

from middlewared.test.integration.utils import mock


@contextlib.contextmanager
def set_fips_available(value=True):
    with mock('system.security.info.fips_available', return_value=value):
        yield
