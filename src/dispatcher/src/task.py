__author__ = 'jceel'

import errno
from rpc.rpc import RpcService, RpcException

class Task(object):
    SUCCESS = (0, "Success")

    @classmethod
    def _get_metadata(cls):
        return {
            'description': cls._description if hasattr(cls, '_description') else None,
            'schema': cls._schema if hasattr(cls, '_schema') else None
        }

    def get_status(self):
        return TaskStatus(50, 'Executing...')

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

def description(descr):
    def wrapped(fn):
        fn._description = descr
        return fn

    return wrapped


def schema(*sch):
    def wrapped(fn):
        fn._schema = sch
        return fn

    return wrapped


def require_roles(*roles):
    def wrapped(fn):
        fn._roles_required = roles
        return fn

    return wrapped