import contextlib
import threading
import typing

from middlewared.test.integration.assets.crypto import get_cert_params, root_certificate_authority
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import client


def event_thread(event_endpoint: str, context: dict):
    with client(py_exceptions=False) as c:
        def cb(mtype, **message):
            if len(message) != 3 or not all(
                k in message for k in ('id', 'msg', 'collection')
            ) or message['collection'] != event_endpoint or message['msg'] not in (
                'added', 'changed', 'removed'
            ):
                return

            if context['result'] is None:
                context['result'] = message

            context['received_result'].set()
            context['shutdown_thread'].set()

        c.subscribe(event_endpoint, cb)
        context['subscribed'].set()
        context['shutdown_thread'].wait(context['timeout'])


@contextlib.contextmanager
def wait_for_event(event_endpoint: str, timeout=60):
    context = {
        'subscribed': threading.Event(),
        'result': None,
        'received_result': threading.Event(),
        'shutdown_thread': threading.Event(),
        'timeout': timeout,
    }
    thread = threading.Thread(target=event_thread, args=(event_endpoint, context), daemon=True)
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
    assert context['result'] == {
        'msg': event_type,
        'collection': event_endpoint,
        'id': oid,
    }


def test_event_create_on_non_job_method():
    with wait_for_event('certificateauthority.query') as context:
        with root_certificate_authority('root_ca_create_event_test') as root_ca:
            assert root_ca['CA_type_internal'] is True, root_ca

    assert_result(context, 'certificateauthority.query', root_ca['id'], 'added')


def test_event_create_on_job_method():
    with root_certificate_authority('root_ca_create_event_test') as root_ca:
        with wait_for_event('certificate.query') as context:
            cert = call('certificate.create', {
                'name': 'cert_test',
                'signedby': root_ca['id'],
                'create_type': 'CERTIFICATE_CREATE_INTERNAL',
                **get_cert_params(),
            }, job=True)
            try:
                assert cert['cert_type_internal'] is True, cert
            finally:
                call('certificate.delete', cert['id'], job=True)

        assert_result(context, 'certificate.query', cert['id'], 'added')


def test_event_update_on_non_job_method():
    with root_certificate_authority('root_ca_update_event_test') as root_ca:
        assert root_ca['CA_type_internal'] is True, root_ca

        with wait_for_event('certificateauthority.query') as context:
            call('certificateauthority.update', root_ca['id'], {})

        assert_result(context, 'certificateauthority.query', root_ca['id'], 'changed')


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
    root_ca = call('certificateauthority.create', {
        **get_cert_params(),
        'name': 'test_root_ca_delete_event',
        'create_type': 'CA_CREATE_INTERNAL',
    })
    assert root_ca['CA_type_internal'] is True, root_ca

    with wait_for_event('certificateauthority.query') as context:
        call('certificateauthority.delete', root_ca['id'])

    assert_result(context, 'certificateauthority.query', root_ca['id'], 'removed')


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
