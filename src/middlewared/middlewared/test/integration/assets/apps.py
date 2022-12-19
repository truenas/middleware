import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def chart_release(payload: dict):
    release_data = call('chart.release.create', payload, job=True)
    try:
        yield release_data
    finally:
        call('chart.release.delete', release_data['id'], job=True)
