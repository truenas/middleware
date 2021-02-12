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
        self._cancel = threading.Event()

    def process(self):
        try:
            self.run()
        except Exception:
            self.middleware.logger.warning('EventSource %r run() failed', self.name, exc_info=True)

        try:
            self.on_finish()
        except Exception:
            self.middleware.logger.warning('EventSource %r on_finish() failed', self.name, exc_info=True)

        self.middleware.run_coroutine(self.unsubscribe_all())

    def run(self):
        raise NotImplementedError('run() method not implemented')

    def cancel(self):
        self._cancel.set()

    def on_finish(self):
        pass
