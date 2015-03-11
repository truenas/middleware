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


import errno
import psutil
from task import Task, TaskStatus, Provider, TaskException
from dispatcher.rpc import RpcException, description, accepts, returns
from utils import first_or_default


@description("Provides info about configured AFP shares")
class AFPSharesProvider(Provider):
    def get_connected_clients(self, share_name):
        result = []
        for i in psutil.process_iter():
            if i.name() != 'afpd':
                continue

            conns = filter(lambda c: c.pid == i.pid, psutil.net_connections('inet'))
            conn = first_or_default(lambda c: c.laddr[1] == 548, conns)

            if not conn:
                continue

            result.append({
                'host': conn.laddr[0],
                'share': None,
                'user': i.username()
            })


@description("Adds new AFP share")
@accepts({
    'title': 'share',
    '$ref': 'afp-share'
})
class CreateAFPShareTask(Task):
    def describe(self, share):
        return "Creating AFP share {0}".format(share['id'])

    def verify(self, share):
        return ['service:afp']

    def run(self, share):
        self.datastore.insert('shares', share)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'afp')
        self.dispatcher.call_sync('services.ensure_started', 'afp')
        self.dispatcher.call_sync('services.reload', 'afp')
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
    '$ref': 'afp-share'
})
class UpdateAFPShareTask(Task):
    def describe(self, name, updated_fields):
        return "Updating AFP share {0}".format(name)

    def verify(self, name, updated_fields):
        return ['service:afp']

    def run(self, name, updated_fields):
        share = self.datastore.get_by_id('shares', name)
        share.update(updated_fields)
        self.datastore.update('shares', name, share)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'afp')
        self.dispatcher.call_sync('services.reload', 'afp')
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
        self.datastore.delete('shares', name)
        self.dispatcher.call_sync('etcd.generation.generate_group', 'afp')
        self.dispatcher.call_sync('services.reload', 'afp')
        self.dispatcher.dispatch_event('shares.afp.changed', {
            'operation': 'delete',
            'ids': [name]
        })


def _metadata():
    return {
        'type': 'sharing',
        'method': 'afp'
    }


def _init(dispatcher):
    dispatcher.register_schema_definition('afp-share', {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'comment': {'type': 'string'},
            'read-only': {'type': 'boolean'},
            'time-machine': {'type': 'boolean'},
            'ro-list': {
                'type': 'array',
                'items': {'type': 'string'}
            },
            'rw-list': {
                'type': ['array', 'null'],
                'items': {'type': 'string'}
            },
            'users-allow': {
                'type': ['array', 'null'],
                'items': {'type': 'string'}
            },
            'users-deny': {
                'type': ['array', 'null'],
                'items': {'type': 'string'}
            },
            'hosts-allow': {
                'type': ['array', 'null'],
                'items': {'type': 'string'}
            },
            'hosts-deny': {
                'type': ['array', 'null'],
                'items': {'type': 'string'}
            },
        }
    })

    dispatcher.register_task_handler("share.afp.create", CreateAFPShareTask)
    dispatcher.register_task_handler("share.afp.update", UpdateAFPShareTask)
    dispatcher.register_task_handler("share.afp.delete", DeleteAFPShareTask)
    dispatcher.register_provider("shares.afp", AFPSharesProvider)
    dispatcher.register_resource('service:netatalk', ['system'])
