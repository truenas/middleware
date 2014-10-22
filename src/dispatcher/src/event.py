__author__ = 'jceel'

import logging

class EventSource(object):
    def __init__(self, dispatcher):
        self.__dispatcher = dispatcher
        self.__logger = logging.getLogger(self.__class__.__name__)

    def register_event_type(self, name):
        pass

    def emit_event(self, type, **kwargs):
        self.__dispatcher.dispatch_event(type, kwargs)

    def listen_for_event(self, type, handler):
        pass