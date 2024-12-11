import contextlib

from middlewared.test.integration.utils import mock


@contextlib.contextmanager
def set_fips_available(value=True):
    with mock('system.security.info.fips_available', return_value=value):
        yield


@contextlib.contextmanager
def product_type(product_type='SCALE_ENTERPRISE'):
    with mock('system.product_type', return_value=product_type):
        yield


@contextlib.contextmanager
def enable_stig():
    with product_type():
        with mock('system.security.config', return_value={'id': 1, 'enable_fips': True, 'enable_gpos_stig': True}):
            yield
