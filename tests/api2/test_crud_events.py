import typing

from middlewared.test.integration.assets.crypto import certificate_signing_request
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, wait_for_event


def assert_result(context: dict, event_endpoint: str, oid: typing.Union[int, str], event_type: str) -> None:
    expected = {
        'msg': event_type,
        'collection': event_endpoint,
        'id': oid,
    }
    assert all(context['result'].get(k) == v for k, v in expected.items()), context


def test_event_create_on_non_job_method():
    with wait_for_event('pool.dataset.query', expected_collection_type='added') as context:
        with dataset('create_crud') as ds:
            pass

    assert_result(context, 'pool.dataset.query', ds, 'added')


def test_event_create_on_job_method():
    with wait_for_event('certificate.query') as context:
        with certificate_signing_request('csr_event_test_job_method') as csr:
            pass

    assert_result(context, 'certificate.query', csr['id'], 'added')


def test_event_update_on_non_job_method():
    with dataset('update_crud') as ds:
        with wait_for_event('pool.dataset.query') as context:
            call('pool.dataset.update', ds, {})

        assert_result(context, 'pool.dataset.query', ds, 'changed')


def test_event_update_on_job_method():
    with wait_for_event('tunable.query'):
        tunable = call('tunable.create', {
            'type': 'SYSCTL',
            'var': 'kernel.watchdog',
            'value': '1',
        }, job=True)
        try:
            with wait_for_event('tunable.query') as context:
                call('tunable.update', tunable['id'], {'value': '0'}, job=True)

            assert_result(context, 'tunable.query', tunable['id'], 'changed')
        finally:
            call('tunable.delete', tunable['id'], job=True)


def test_event_delete_on_non_job_method():
    with wait_for_event('pool.dataset.query', expected_collection_type='removed') as context:
        with dataset('delete_crud') as ds:
            pass

    assert_result(context, 'pool.dataset.query', ds, 'removed')


def test_event_delete_on_job_method():
    with wait_for_event('tunable.query'):
        tunable = call('tunable.create', {
            'type': 'SYSCTL',
            'var': 'kernel.watchdog',
            'value': '1',
        }, job=True)

    with wait_for_event('tunable.query') as context:
        call('tunable.delete', tunable['id'], job=True)

    assert_result(context, 'tunable.query', tunable['id'], 'removed')
