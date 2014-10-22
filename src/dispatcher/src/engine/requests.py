# coding=utf-8
import weakref
from webob.response import Response as WSGIResponse


class Request(WSGIResponse):
    """
    The request which provides end function to easily end the response and send it out
    """

    def __init__(self, handler, *args, **kwargs):
        super(Request, self).__init__(*args, **kwargs)
