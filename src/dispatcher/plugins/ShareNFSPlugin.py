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

import os
import errno
from gevent import Timeout
from watchdog import events
from task import Task, TaskStatus, Provider, TaskException
from dispatcher.rpc import RpcException, description, accepts, returns
from balancer import TaskState
from event import EventSource
from lib.system import system, SubprocessException


@description("Provides info about configured NFS shares")
class NFSSharesProvider(Provider):
    def initialize(self, context):
        self.datastore = context.dispatcher.datastore

    @description("Lists configured NFS shares")
    @returns({
        'type': 'array',
        'items': {'$ref': 'definitions/nfs-share'}
    })
    def query(self, filter=None, params=None):
        return self.datastore.query('shares.nfs', *(filter or []), **(params or {}))

    def get_connected_users(self, share):
        pass


@description("Adds new NFS share")
@accepts({
    'title': 'share',
    '$ref': 'definitions/nfs-share'
})
class CreateNFSShareTask(Task):
    def describe(self, share):
        return "Creating NFS share {0}".format(share['id'])

    def verify(self, share):
        return ['service:nfs']

    def run(self, share):
        self.datastore.insert('shares.nfs', share)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'nfs')
        self.dispatcher.call_sync('service.reload', 'nfs')
        self.dispatcher.dispatch_event('shares.nfs.changed', {
            'operation': 'create',
            'ids': [share['id']]
        })


@description("Updates existing NFS share")
@accepts({
    'title': 'name',
    'type': 'string'
}, {
    'title': 'share',
    '$ref': 'definitions/nfs-share'
})
class UpdateNFSShareTask(Task):
    def describe(self, name):
        return "Updating NFS share {0}".format(name)

    def verify(self, name):
        return ['service:nfs']

    def run(self, name, updated_fields):
        self.datastore.update('shares.nfs', name, updated_fields)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'nfs')
        self.dispatcher.call_sync('service.reload', 'nfs')
        self.dispatcher.dispatch_event('shares.nfs.changed', {
            'operation': 'update',
            'ids': [name]
        })



@description("Removes NFS share")
@accepts({
    'title': 'name',
    'type': 'string'
})
class DeleteNFSShareTask(Task):
    def describe(self, name):
        return "Deleting NFS share {0}".format(name)

    def verify(self, name):
        return ['service:nfs']

    def run(self, name):
        self.datastore.delete('shares.nfs', name)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'nfs')
        self.dispatcher.call_sync('service.reload', 'nfs')
        self.dispatcher.dispatch_event('shares.nfs.changed', {
            'operation': 'delete',
            'ids': [name]
        })


def _init(dispatcher):
    dispatcher.register_schema_definition('nfs-share', {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'comment': {'type': 'string'},
            'alldirs': {'type': 'boolean'},
            'read-only': {'type': 'boolean'},
            'maproot-user': {'type': 'string'},
            'maproot-group': {'type': 'string'},
            'mapall-user': {'type': 'string'},
            'mapall-group': {'type': 'string'},
            'hosts': {
                'type': 'array',
                'items': {'type': 'string'}
            },
            'paths': {
                'type': 'array',
                'items': {'type': 'string'}
            }
        }
    })

    dispatcher.register_task_handler("share.nfs.create", CreateNFSShareTask)
    dispatcher.register_task_handler("share.nfs.update", UpdateNFSShareTask)
    dispatcher.register_task_handler("share.nfs.delete", DeleteNFSShareTask)
    dispatcher.register_provider("share.nfs", NFSSharesProvider)
    dispatcher.register_resource('service:nfs', ['system'])