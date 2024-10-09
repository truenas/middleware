import contextlib

from middlewared.test.integration.utils import mock


@contextlib.contextmanager
def product_type(product_type='SCALE_ENTERPRISE'):
    with mock('system.product_type', return_value=product_type):
        yield
