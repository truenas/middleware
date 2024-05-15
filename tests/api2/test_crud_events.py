import contextlib
import threading
import typing

from middlewared.test.integration.assets.crypto import get_cert_params, root_certificate_authority
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import client


def event_thread(event_endpoint: str, context: dict):
    with client(py_exceptions=False) as c:
        context['start_event'].set()
        subscribe_payload = c.event_payload()
        event = subscribe_payload['event']
        context['event'] = event

        def cb(mtype, **message):
            if len(message) != 3 or not all(
                k in message for k in ('id', 'msg', 'collection')
            ) or message['collection'] != event_endpoint or message['msg'] not in (
                'added', 'changed', 'removed'
            ):
                return

            context['result'] = message
            event.set()

        c.subscribe(event_endpoint, cb, subscribe_payload)
        if not event.wait(timeout=context['timeout']):
            raise Exception('Timed out waiting for CRUD event to be generated')


@contextlib.contextmanager
def gather_events(event_endpoint: str, context_args: dict = None):
    context = {
        'result': None,
        'event': None,
        'start_event': threading.Event(),
        'timeout': 60,
        **(context_args or {})
    }
    thread = threading.Thread(target=event_thread, args=(event_endpoint, context), daemon=True)
    thread.start()
    if not context['start_event'].wait(timeout=30):
        raise Exception('Timed out waiting for event thread to start')

    try:
        yield context
    finally:
        if context['event'] and context['event'].is_set() is False:
            context['event'].set()
        thread.join(timeout=5)


def assert_result(context: dict, event_endpoint: str, oid: typing.Union[int, str], event_type: str) -> None:
    assert context['result'] == {
        'msg': event_type,
        'collection': event_endpoint,
        'id': oid,
    }


def test_event_create_on_non_job_method():
    with gather_events('certificateauthority.query') as context:
        with root_certificate_authority('root_ca_create_event_test') as root_ca:
            assert root_ca['CA_type_internal'] is True, root_ca
            assert_result(context, 'certificateauthority.query', root_ca['id'], 'added')


def test_event_create_on_job_method():
    with gather_events('certificate.query') as context:
        with root_certificate_authority('root_ca_create_event_test') as root_ca:
            cert = call('certificate.create', {
                'name': 'cert_test',
                'signedby': root_ca['id'],
                'create_type': 'CERTIFICATE_CREATE_INTERNAL',
                **get_cert_params(),
            }, job=True)
            try:
                assert cert['cert_type_internal'] is True, cert
                assert_result(context, 'certificate.query', cert['id'], 'added')
            finally:
                call('certificate.delete', cert['id'], job=True)


def test_event_update_on_non_job_method():
    with root_certificate_authority('root_ca_update_event_test') as root_ca:
        with gather_events('certificateauthority.query') as context:
            assert root_ca['CA_type_internal'] is True, root_ca
            assert context['result'] is None, context

            call('certificateauthority.update', root_ca['id'], {})

            assert_result(context, 'certificateauthority.query', root_ca['id'], 'changed')


def test_event_update_on_job_method():
    tunable = call('tunable.create', {
        'type': 'SYSCTL',
        'var': 'kernel.watchdog',
        'value': '1',
    }, job=True)
    try:
        with gather_events('tunable.query') as context:
            call('tunable.update', tunable['id'], {'value': '0'}, job=True)
            assert_result(context, 'tunable.query', tunable['id'], 'changed')
    finally:
        call('tunable.delete', tunable['id'], job=True)


def test_event_delete_on_non_job_method():
    root_ca = call('certificateauthority.create', {
        **get_cert_params(),
        'name': 'test_root_ca_delete_event',
        'create_type': 'CA_CREATE_INTERNAL',
    })
    with gather_events('certificateauthority.query') as context:
        assert root_ca['CA_type_internal'] is True, root_ca
        assert context['result'] is None, context

        call('certificateauthority.delete', root_ca['id'])

        assert_result(context, 'certificateauthority.query', root_ca['id'], 'removed')


def test_event_delete_on_job_method():
    tunable = call('tunable.create', {
        'type': 'SYSCTL',
        'var': 'kernel.watchdog',
        'value': '1',
    }, job=True)
    with gather_events('tunable.query') as context:
        call('tunable.delete', tunable['id'], job=True)
        assert_result(context, 'tunable.query', tunable['id'], 'removed')
