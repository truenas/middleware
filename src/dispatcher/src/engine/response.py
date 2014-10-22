# coding=utf-8
from pyee import EventEmitter
from webob.response import Response as WSGIResponse
from gevent.event import Event


class Response(WSGIResponse, EventEmitter):

    class ResponseAlreadyEnded(Exception):
        pass

    def __init__(self, *args, **kwargs):
        self.event = Event()
        super(Response, self).__init__(*args, **kwargs)
        EventEmitter.__init__(self)

    def end(self, status_code=None, body=None):
        self.emit('pre_end')
        if self.event.is_set():
            raise Response.ResponseAlreadyEnded('response already ended, did you call response.end() several times?')

        if status_code is not None:
            self.status_code = status_code

        if body is not None:
            self.body = body

        self.event.set()
        self.emit('post_end')

    def join(self):
        return self.event.wait()

    @property
    def is_set(self):
        return self.event.is_set()
