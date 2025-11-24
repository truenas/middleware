import contextlib
import threading
import typing

from middlewared.test.integration.assets.crypto import certificate_signing_request
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import client


def event_thread(event_endpoint: str, context: dict, expected_collection_type: str | None = None):
    call('rate.limit.cache_clear')
    with client(py_exceptions=False) as c:
        def cb(mtype, **message):
            if not all(
                k in message for k in ('id', 'msg', 'collection')
            ) or message['collection'] != event_endpoint or message['msg'] not in (
                'added', 'changed', 'removed'
            ) or (expected_collection_type is not None and message['msg'] != expected_collection_type):
                return

            if context['result'] is None:
                context['result'] = message

            context['received_result'].set()
            context['shutdown_thread'].set()

        c.subscribe(event_endpoint, cb)
        context['subscribed'].set()
        context['shutdown_thread'].wait(context['timeout'])


@contextlib.contextmanager
def wait_for_event(event_endpoint: str, timeout=60, expected_collection_type: str | None = None):
    context = {
        'subscribed': threading.Event(),
        'result': None,
        'received_result': threading.Event(),
        'shutdown_thread': threading.Event(),
        'timeout': timeout,
    }
    thread = threading.Thread(
        target=event_thread, args=(event_endpoint, context, expected_collection_type), daemon=True,
    )
    thread.start()
    if not context['subscribed'].wait(30):
        raise Exception('Timed out waiting for client to subscribe')

    try:
        yield context
        if not context['received_result'].wait(timeout):
            raise Exception('Event not received')
    finally:
        context['shutdown_thread'].set()
        thread.join(timeout=5)


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
