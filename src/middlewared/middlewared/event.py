import asyncio
import threading


class Events(object):

    def __init__(self):
        self.__events = {}
        self.__events_private = set()

    def register(self, name, description, private=False):
        if name in self.__events:
            raise ValueError(f'Event {name!r} already registered.')
        self.__events[name] = description
        if private:
            self.__events_private.add(name)

    def __contains__(self, name):
        return name in self.__events

    def __iter__(self):
        for k, v in self.__events.items():
            yield k, {
                'description': v,
                'private': k in self.__events_private,
                'wildcard_subscription': True
            }


class EventSource(object):

    def __init__(self, middleware, name, arg, send_event, unsubscribe_all):
        self.middleware = middleware
        self.name = name
        self.arg = arg
        self.send_event = send_event
        self.unsubscribe_all = unsubscribe_all
        self._cancel = asyncio.Event()
        self._cancel_sync = threading.Event()

    async def process(self):
        try:
            await self.run()
        except Exception:
            self.middleware.logger.error('EventSource %r run() failed', self.name, exc_info=True)
        try:
            await self.on_finish()
        except Exception:
            self.middleware.logger.error('EventSource %r on_finish() failed', self.name, exc_info=True)

        await self.unsubscribe_all()

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
