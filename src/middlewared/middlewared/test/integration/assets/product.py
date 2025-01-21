import contextlib

from middlewared.test.integration.utils import mock


@contextlib.contextmanager
def set_fips_available(value=True):
    with mock('system.security.info.fips_available', return_value=value):
        yield


@contextlib.contextmanager
def product_type(product_type='ENTERPRISE'):
    with mock('system.product_type', return_value=product_type):
        yield


@contextlib.contextmanager
def set_stig_available():
    with product_type():
        with set_fips_available():
            yield
