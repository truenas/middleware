import asyncio
import contextlib
import json
import threading
import typing

from middlewared.role import RoleManager
from middlewared.schema import Any, clean_and_validate_arg, ValidationErrors


class Events:
    def __init__(self, role_manager: RoleManager):
        self.role_manager = role_manager
        self._events: typing.Dict[str, dict[str, typing.Any]] = {}
        self.__events_private: typing.Set[str] = set()

    def register(self, name: str, description: str, private: bool, returns, models, no_auth_required,
                 no_authz_required, roles: typing.Iterable[str]):
        if name in self._events:
            raise ValueError(f'Event {name!r} already registered.')
        self.role_manager.register_event(name, roles)
        self._events[name] = {
            'description': description,
            'accepts': [],
            'returns': [returns] if returns else [Any(name, null=True)],
            'models': models,
            'no_auth_required': no_auth_required,
            'no_authz_required': no_authz_required,
            'roles': self.role_manager.roles_for_event(name),
        }
        if private:
            self.__events_private.add(name)

    def get_event(self, name: str) -> typing.Optional[dict[str, typing.Any]]:
        event = self._events.get(name)
        if event is None:
            return None

        return {
            'private': name in self.__events_private,
            'wildcard_subscription': True,
            **event,
        }

    def __contains__(self, name):
        return name in self._events

    def __iter__(self):
        for k in self._events:
            yield k, self.get_event(k)


class EventSourceMetabase(type):

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if name == 'EventSource' and bases == ():
            return klass

        for i in (('ACCEPTS', name.lower()), ('RETURNS', f'{name.lower()}_returns')):
            doc_type = getattr(klass, i[0])
            if doc_type == NotImplementedError:
                doc_type = Any(null=True)
            if not doc_type.name:
                doc_type.name = i[1]
            setattr(klass, i[0], [doc_type])

        return klass


class EventSource(metaclass=EventSourceMetabase):

    ACCEPTS = NotImplementedError
    RETURNS = NotImplementedError

    def __init__(self, middleware, name, arg, send_event, unsubscribe_all):
        self.middleware = middleware
        self.name = name
        self.arg = arg
        self.send_event_internal = send_event
        self.unsubscribe_all = unsubscribe_all
        self._cancel = asyncio.Event()
        self._cancel_sync = threading.Event()

    def send_event(self, event_type: str, **kwargs):
        self.send_event_internal(event_type, **kwargs)

    async def validate_arg(self):
        verrors = ValidationErrors()
        try:
            with contextlib.suppress(json.JSONDecodeError):
                self.arg = json.loads(self.arg)
        except TypeError:
            self.arg = self.ACCEPTS[0].default

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
