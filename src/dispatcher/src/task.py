__author__ = 'jceel'

import errno
from rpc.rpc import RpcService, RpcException

class Task(object):
    SUCCESS = (0, "Success")

    def chain(self, task, **kwargs):
        pass


class TaskException(RpcException):
    pass

class TaskStatus(object):
    def __init__(self, percentage, message=None, extra=None):
        self.percentage = percentage
        self.message = message
        self.extra = extra

    def __getstate__(self):
        return {
            'percentage': self.percentage,
            'message': self.message,
            'extra': self.extra
        }

class Provider(RpcService):
    def initialize(self, context):
        pass