import threading


class EventSource(object):

    def __init__(self, middleware, app, name, arg):
        self.middleware = middleware
        self.app = app
        self.name = name
        self.arg = arg
        self._cancel = threading.Event()

    def send_event(self, etype, **kwargs):
        self.app.send_event(self.name, etype, **kwargs)

    def process(self):
        self.run()

    def run(self):
        raise NotImplementedError('run() method not implemented')

    def cancel(self):
        self._cancel.set()
