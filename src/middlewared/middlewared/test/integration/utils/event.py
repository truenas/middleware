import contextlib
import threading

from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import client

__all__ = ["wait_for_event"]


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
