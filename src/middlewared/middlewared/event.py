import asyncio
import contextlib
import json
import threading

from middlewared.schema import Any, clean_and_validate_arg, ValidationErrors
from middlewared.settings import conf


class Events(object):

    def __init__(self):
        self._events = {}
        self.__events_private = set()

    def register(self, name, description, private=False, returns=None):
        if name in self._events:
            raise ValueError(f'Event {name!r} already registered.')
        self._events[name] = {
            'description': description,
            'accepts': [],
            'returns': list(returns) if returns else [],
        }
        if private:
            self.__events_private.add(name)

    def __contains__(self, name):
        return name in self._events

    def __iter__(self):
        for k, v in self._events.items():
            yield k, {
                'private': k in self.__events_private,
                'wildcard_subscription': True,
                **v,
            }


class EventSource(object):

    ACCEPTS = Any(null=True)
    RETURNS = Any(null=True)

    def __init__(self, middleware, name, arg, send_event, unsubscribe_all):
        self.middleware = middleware
        self.name = name
        self.arg = arg
        self.send_event_internal = send_event
        self.unsubscribe_all = unsubscribe_all
        self._cancel = asyncio.Event()
        self._cancel_sync = threading.Event()
        for i in (('ACCEPTS', name.replace('.', '_')), ('RETURNS', f'{name.replace(".", "_")}_returns')):
            doc_type = getattr(self, i[0])
            doc_type.name = i[1]
            setattr(self, i[0], [doc_type])

    def send_event(self, event_type, **kwargs):
        if conf.debug_mode and event_type in ('ADDED', 'CHANGED'):
            verrors = ValidationErrors()
            clean_and_validate_arg(verrors, self.RETURNS[0], kwargs.get('fields'))
            if verrors:
                asyncio.ensure_future(self.unsubscribe_all(verrors))
                return

        self.send_event_internal(event_type, **kwargs)

    async def validate_arg(self):
        verrors = ValidationErrors()
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            self.arg = json.loads(self.arg)

        self.arg = clean_and_validate_arg(verrors, self.ACCEPTS[0], self.arg)
        verrors.check()

    async def process(self):
        error = None
        try:
            await self.run()
        except Exception as e:
            error = e
            self.middleware.logger.error('EventSource %r run() failed', self.name, exc_info=True)
        try:
            await self.on_finish()
        except Exception:
            self.middleware.logger.error('EventSource %r on_finish() failed', self.name, exc_info=True)

        await self.unsubscribe_all(error)

    async def run(self):
        await self.middleware.run_in_thread(self.run_sync)

    def run_sync(self):
        raise NotImplementedError('run_sync() method not implemented')

    async def cancel(self):
        self._cancel.set()
        await self.middleware.run_in_thread(self._cancel_sync.set)

    async def on_finish(self):
        await self.middleware.run_in_thread(self.on_finish_sync)

    def on_finish_sync(self):
        pass
