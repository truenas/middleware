import asyncio
import errno
import functools
import sys

from collections import defaultdict, namedtuple

from middlewared.event import EventSource
from middlewared.schema import ValidationErrors

IdentData = namedtuple("IdentData", ["app", "name", "arg"])


class EventSourceManager:
    def __init__(self, middleware):
        self.middleware = middleware

        self.event_sources = {}
        self.instances = defaultdict(dict)
        self.idents = {}
        self.subscriptions = defaultdict(lambda: defaultdict(set))

    def short_name_arg(self, name):
        if ':' in name:
            shortname, arg = name.split(':', 1)
        else:
            shortname = name
            arg = None
        return shortname, arg

    def get_full_name(self, name, arg):
        if arg is None:
            return name
        else:
            return f'{name}:{arg}'

    def register(self, name, event_source):
        if not issubclass(event_source, EventSource):
            raise RuntimeError(f"{event_source} is not EventSource subclass")

        self.event_sources[name] = event_source

    async def subscribe(self, app, ident, name, arg):
        if ident in self.idents:
            raise ValueError(f"Ident {ident} is already used")

        self.idents[ident] = IdentData(app, name, arg)
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
                await self.unsubscribe(
                    ident, app.get_error_dict(errno.EAGAIN, str(e), sys.exc_info(), etype='VALIDATION', extra=list(e))
                )
            else:
                asyncio.ensure_future(self.instances[name][arg].process())
        else:
            self.middleware.logger.trace("Re-using existing instance of event source %r:%r", name, arg)

    async def unsubscribe(self, ident, error=None):
        ident_data = self.idents.pop(ident)
        await self.send_no_sub_message(ident_data, error)

        idents = self.subscriptions[ident_data.name][ident_data.arg]
        idents.remove(ident)
        if not idents:
            self.middleware.logger.trace("Canceling instance of event source %r:%r as the last subscriber "
                                         "unsubscribed", ident_data.name, ident_data.arg)
            instance = self.instances[ident_data.name].pop(ident_data.arg)
            await instance.cancel()

    async def send_no_sub_message(self, ident, error=None):
        error = {'error': error} if error else {}
        ident.app._send({'msg': 'nosub', 'collection': self.get_full_name(ident.name, ident.arg), **error})

    async def unsubscribe_app(self, app):
        for ident, ident_data in list(self.idents.items()):
            if ident_data.app == app:
                await self.unsubscribe(ident)

    def _send_event(self, name, arg, event_type, **kwargs):
        for ident in list(self.subscriptions[name][arg]):
            try:
                ident_data = self.idents[ident]
            except KeyError:
                self.middleware.logger.trace("Ident %r is gone", ident)
                continue

            ident_data.app.send_event(self.get_full_name(name, arg), event_type, **kwargs)

    async def _unsubscribe_all(self, name, arg, error=None):
        for ident in self.subscriptions[name][arg]:
            await self.send_no_sub_message(self.idents.pop(ident), error)

        self.subscriptions[name][arg].clear()
