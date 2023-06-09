import functools
import os
import sys

from middlewared.client import Client
from middlewared.test.integration.utils.client import host_websocket_uri, password


sys.path.append(os.getcwd())


@functools.cache
def auth():
    return 'root', password()


def event_thread(event_endpoint: str):
    with Client(host_websocket_uri(), py_exceptions=False) as c:
        c.call('auth.login', *auth())

        event_msg = None
        subscribe_payload = c.event_payload()
        event = subscribe_payload['event']

        def cb(mtype, **message):
            nonlocal event_msg
            if len(message) != 3 or not all(
                k in message for k in ('id', 'msg', 'collection')
            ) or message['collection'] != event_endpoint or message['msg'] not in (
                'added', 'changed', 'removed'
            ):
                return

            event_msg = message
            event.set()

        c.subscribe(event_endpoint, cb, subscribe_payload)

        if not event.wait():
            return event_msg

        if subscribe_payload['error']:
            return event_msg

        return event_msg
