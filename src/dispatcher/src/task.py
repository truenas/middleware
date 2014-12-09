#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

from dispatcher.rpc import RpcService, RpcException


class Task(object):
    SUCCESS = (0, "Success")

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.datastore = dispatcher.datastore

    @classmethod
    def _get_metadata(cls):
        return {
            'description': cls.description if hasattr(cls, 'description') else None,
            'schema': cls.params_schema if hasattr(cls, 'params_schema') else None
        }

    def get_status(self):
        return TaskStatus(50, 'Executing...')

    def run_subtask(self, classname, *args):
        return self.dispatcher.balancer.run_subtask(self, classname, args)

    def join_subtasks(self, *tasks):
        return self.dispatcher.balancer.join_subtasks(*tasks)

    def chain(self, task, *args):
        self.dispatcher.balancer.submit(task, *args)


class TaskException(RpcException):
    pass


class VerifyException(TaskException):
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
        self.dispatcher = context.dispatcher
        self.datastore = self.dispatcher.datastore


def query(fn):
    fn.params_schema = [
        {
            'title': 'filter',
            'type': 'array',
            'items': {
                'type': 'array',
                'minItems': 3,
                'maxItems': 3
            }
        },
        {
            'title': 'options',
            'type': 'object',
            'properties': {
                'sort-field': {'type': 'string'},
                'sort-order': {'type': 'string', 'enum': ['asc', 'desc']},
                'limit': {'type': 'integer'},
                'offset': {'type': 'integer'},
                'single': {'type': 'boolean'}
            }
        }
    ]
    return fn