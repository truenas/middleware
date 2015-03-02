#+
# Copyright 2015 iXsystems, Inc.
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

import os
import errno
from gevent import Timeout
from watchdog import events
from task import Task, TaskStatus, Provider, TaskException
from dispatcher.rpc import RpcException, description, accepts, returns
from balancer import TaskState
from event import EventSource
from lib.system import system, SubprocessException


@description("Provides info about configured AFP shares")
class AFPSharesProvider(Provider):
    def initialize(self, context):
        self.datastore = context.dispatcher.datastore

    @description("Lists configured AFP shares")
    @returns({
        'type': 'array',
        'items': {'$ref': 'definitions/afp-share'}
    })
    def query(self, filter=None, params=None):
        return self.datastore.query('shares.afp', *(filter or []), **(params or {}))

    def get_connected_users(self, share):
        pass


@description("Adds new AFP share")
@accepts({
    'title': 'share',
    '$ref': 'definitions/afp-share'
})
class CreateAFPShareTask(Task):
    def describe(self, share):
        return "Creating AFP share {0}".format(share['id'])

    def verify(self, share):
        return ['service:afp']

    def run(self, share):
        self.datastore.insert('shares.afp', share)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'afp')
        self.dispatcher.call_sync('service.reload', 'afp')
        self.dispatcher.dispatch_event('shares.afp.changed', {
            'operation': 'create',
            'ids': [share['id']]
        })


@description("Updates existing AFP share")
@accepts({
    'title': 'name',
    'type': 'string'
}, {
    'title': 'share',
    '$ref': 'definitions/afp-share'
})
class UpdateAFPShareTask(Task):
    def describe(self, name):
        return "Updating AFP share {0}".format(name)

    def verify(self, name):
        return ['service:afp']

    def run(self, name, updated_fields):
        self.datastore.update('shares.afp', name, updated_fields)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'afp')
        self.dispatcher.call_sync('service.reload', 'afp')
        self.dispatcher.dispatch_event('shares.afp.changed', {
            'operation': 'update',
            'ids': [name]
        })



@description("Removes AFP share")
@accepts({
    'title': 'name',
    'type': 'string'
})
class DeleteAFPShareTask(Task):
    def describe(self, name):
        return "Deleting AFP share {0}".format(name)

    def verify(self, name):
        return ['service:afp']

    def run(self, name):
        self.datastore.delete('shares.afp', name)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'afp')
        self.dispatcher.call_sync('service.reload', 'afp')
        self.dispatcher.dispatch_event('shares.afp.changed', {
            'operation': 'delete',
            'ids': [name]
        })


def _init(dispatcher):
    dispatcher.register_schema_definition('afp-share', {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'comment': {'type': 'string'},
            'read-only': {'type': 'boolean'},
            'time-machine': {'type': 'boolean'},
            'users-allow': {
                'type': 'array',
                'items': {'type': 'string'}
            },
            'users-deny': {
                'type': 'array',
                'items': {'type': 'string'}
            },
            'hosts-allow': {
                'type': 'array',
                'items': {'type': 'string'}
            },
            'hosts-deny': {
                'type': 'array',
                'items': {'type': 'string'}
            },
        }
    })

    dispatcher.register_task_handler("share.afp.create", CreateAFPShareTask)
    dispatcher.register_task_handler("share.afp.update", UpdateAFPShareTask)
    dispatcher.register_task_handler("share.afp.delete", DeleteAFPShareTask)
    dispatcher.register_provider("shares.afp", AFPSharesProvider)
    dispatcher.register_resource('service:netatalk', ['system'])