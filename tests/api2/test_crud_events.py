import contextlib
import functools
import os
import sys
import threading

from middlewared.client import Client
from middlewared.test.integration.utils.client import host_websocket_uri, password


sys.path.append(os.getcwd())


@functools.cache
def auth():
    return 'root', password()


def event_thread(event_endpoint: str, context: dict):
    with Client(host_websocket_uri(), py_exceptions=False) as c:
        c.call('auth.login', *auth())

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
        event.wait(timeout=context['timeout'])


@contextlib.contextmanager
def gather_events(event_endpoint: str):
    context = {'result': None, 'event': None, 'timeout': 300}
    thread = threading.Thread(target=event_thread, args=(event_endpoint, context))
    thread.start()
    try:
        yield context
    finally:
        if context['event']:
            context['event'].set()
        thread.join(timeout=5)
