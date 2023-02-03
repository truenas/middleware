import contextlib
import time

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def chart_release(payload: dict, wait_until_active: bool = False):
    release_data = call('chart.release.create', payload, job=True)
    if wait_until_active:
        while release_data['status'] != 'ACTIVE':
            time.sleep(15)
            release_data = call('chart.release.get_instance', release_data['id'])
    try:
        yield release_data
    finally:
        call('chart.release.delete', release_data['id'], job=True)
