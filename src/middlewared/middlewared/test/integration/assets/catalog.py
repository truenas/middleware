import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def catalog(payload: dict):
    catalog_data = call('catalog_old.create', payload, job=True)
    try:
        yield catalog_data
    finally:
        call('catalog_old.delete', catalog_data['id'])
