import asyncio
import threading


class EventSource(object):

    def __init__(self, middleware, app, ident, name, arg):
        self.middleware = middleware
        self.app = app
        self.ident = ident
        self.name = name
        self.arg = arg
        self._cancel = threading.Event()

    def send_event(self, etype, **kwargs):
        self.app.send_event(self.name, etype, **kwargs)

    def process(self):
        try:
            self.run()
        except Exception:
            self.middleware.warn('EventSource %r run() failed', self.name, exc_info=True)
        try:
            self.on_finish()
        except Exception:
            self.middleware.warn('EventSource %r on_finish() failed', self.name, exc_info=True)
        asyncio.run_coroutine_threadsafe(self.app.unsubscribe(self.ident), self.app.loop)

    def run(self):
        raise NotImplementedError('run() method not implemented')

    def cancel(self):
        self._cancel.set()

    def on_finish(self):
        pass
