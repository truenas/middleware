from __future__ import annotations
import asyncio
from collections import defaultdict
import functools
from typing import Literal, NamedTuple, TypeAlias, TYPE_CHECKING
from uuid import uuid4

from middlewared.event import EventSource
from middlewared.service_exception import ValidationErrors
if TYPE_CHECKING:
    from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketApp
    from middlewared.main import Middleware


class IdentData(NamedTuple):
    subscriber: Subscriber
    name: str
    arg: str | None


class Subscriber:
    def send_event(self, event_type: str, **kwargs):
        raise NotImplementedError

    def terminate(self, error: Exception | None):
        raise NotImplementedError


class AppSubscriber(Subscriber):
    def __init__(self, app: RpcWebSocketApp, collection: str):
        self.app = app
        self.collection = collection

    def send_event(self, event_type, **kwargs):
        self.app.send_event(self.collection, event_type, **kwargs)

    def terminate(self, error):
        self.app.notify_unsubscribed(self.collection, error)


class InternalSubscriber(Subscriber):
    def __init__(self):
        self.iterator = InternalSubscriberIterator()

    def send_event(self, event_type, **kwargs):
        self.iterator.queue.put_nowait((False, (event_type, kwargs)))

    def terminate(self, error):
        if error:
            self.iterator.queue.put_nowait((True, error))
        else:
            self.iterator.queue.put_nowait(None)


_IteratorItem: TypeAlias = tuple[str, dict]
"""Event type and kwargs"""
_InternalIteratorItem: TypeAlias = tuple[Literal[True], Exception] | tuple[Literal[False], _IteratorItem] | None
"""Queue item type for InternalSubscriberIterator:
- (`True`, Exception): Error to be raised during iteration
- (`False`, _IteratorItem): Event data to be yielded to consumer
- `None`: End of iteration signal (StopAsyncIteration)"""


class InternalSubscriberIterator:
    def __init__(self):
        self.queue: asyncio.Queue[_InternalIteratorItem] = asyncio.Queue()

    def __aiter__(self):
        return self

    async def __anext__(self) -> _IteratorItem:
        item = await self.queue.get()

        if item is None:
            raise StopAsyncIteration

        is_error, value = item
        if is_error:
            raise value
        else:
            return value


_EventSourceDict: TypeAlias = dict[str | None, EventSource]
"""Maps event source arguments to their corresponding EventSource instances.
Key is the argument string passed to the event source (None for parameterless sources).
Value is the active EventSource instance for that argument."""
_SubscriptionsDict: TypeAlias = defaultdict[str | None, set[str]]
"""Maps event source arguments to sets of subscriber identifiers.
Key is the argument string passed to the event source (None for parameterless sources).
Value is a set of subscriber identifiers (idents) currently subscribed to that argument."""


class EventSourceManager:
    def __init__(self, middleware: Middleware):
        self.middleware = middleware

        self.event_sources: dict[str, type[EventSource]] = {}
        self.instances: defaultdict[str, _EventSourceDict] = defaultdict(dict)
        self.idents: dict[str, IdentData] = {}
        self.subscriptions: defaultdict[str, _SubscriptionsDict] = defaultdict(lambda: defaultdict(set))

    def short_name_arg(self, name: str) -> tuple[str, str | None]:
        if ':' in name:
            shortname, arg = name.split(':', 1)
        else:
            shortname = name
            arg = None
        return shortname, arg

    def get_full_name(self, name: str, arg: str | None) -> str:
        if arg is None:
            return name
        else:
            return f'{name}:{arg}'

    def register(self, name: str, event_source: type[EventSource]):
        if not issubclass(event_source, EventSource):
            raise RuntimeError(f"{event_source} is not EventSource subclass")

        self.event_sources[name] = event_source

        self.middleware.role_manager.register_event(name, event_source.roles)

    async def subscribe(self, subscriber: Subscriber, ident: str, name: str, arg: str | None):
        if ident in self.idents:
            raise ValueError(f"Ident {ident} is already used")

        self.idents[ident] = IdentData(subscriber, name, arg)
        self.subscriptions[name][arg].add(ident)

        if arg not in self.instances[name]:
            self.middleware.logger.trace("Creating new instance of event source %r:%r", name, arg)
            self.instances[name][arg] = self.event_sources[name](
                self.middleware, name, arg,
                functools.partial(self._send_event, name, arg),
                functools.partial(self._unsubscribe_all, name, arg),
            )
            # Validate that specified `arg` is acceptable wrt event source in question
            try:
                await self.instances[name][arg].validate_arg()
            except ValidationErrors as e:
                await self.unsubscribe(ident, e)
            else:
                self.middleware.create_task(self.instances[name][arg].process())
        else:
            self.middleware.logger.trace("Re-using existing instance of event source %r:%r", name, arg)

    async def unsubscribe(self, ident: str, error: Exception | None = None):
        ident_data = self.idents.pop(ident, None)
        if ident_data is None:
            return

        self.terminate(ident_data, error)
        idents = self.subscriptions[ident_data.name][ident_data.arg]
        idents.remove(ident)
        if not idents:
            self.middleware.logger.trace("Canceling instance of event source %r:%r as the last subscriber "
                                         "unsubscribed", ident_data.name, ident_data.arg)
            instance = self.instances[ident_data.name].pop(ident_data.arg)
            await instance.cancel()

    def terminate(self, ident: IdentData, error: Exception | None = None):
        ident.subscriber.terminate(error)

    async def subscribe_app(self, app: RpcWebSocketApp, ident: str, name: str, arg: str | None):
        await self.subscribe(AppSubscriber(app, self.get_full_name(name, arg)), ident, name, arg)

    async def unsubscribe_app(self, app: RpcWebSocketApp):
        for ident, ident_data in list(self.idents.items()):
            if isinstance(ident_data.subscriber, AppSubscriber) and ident_data.subscriber.app == app:
                await self.unsubscribe(ident)

    async def iterate(self, name: str, arg: str | None) -> InternalSubscriberIterator:
        ident = str(uuid4())
        subscriber = InternalSubscriber()
        await self.subscribe(subscriber, ident, name, arg)
        return subscriber.iterator

    def _send_event(self, name: str, arg: str | None, event_type: str, **kwargs):
        for ident in list(self.subscriptions[name][arg]):
            try:
                ident_data = self.idents[ident]
            except KeyError:
                self.middleware.logger.trace("Ident %r is gone", ident)
                continue

            ident_data.subscriber.send_event(event_type, **kwargs)

    async def _unsubscribe_all(self, name: str, arg: str | None, error: Exception | None = None):
        for ident in self.subscriptions[name][arg]:
            self.terminate(self.idents.pop(ident), error)

        self.instances[name].pop(arg, None)
        self.subscriptions[name][arg].clear()
