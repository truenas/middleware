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
import signal
import launchd
from task import Task, Provider, TaskException, VerifyException, query
from resources import Resource
from dispatcher.rpc import RpcException, description, accepts, private
from dispatcher.rpc import SchemaHelper as h
from fnutils import template


GETTY_TEMPLATE = {
    'Label': 'org.freebsd.getty.{vt}',
    'RunAtLoad': True,
    'KeepAlive': True,
    'ProgramArguments': [
        '/libexec/getty'
        '{type}',
        '{vt}'
    ]
}


@description("Provides info about available services and their state")
class ServiceInfoProvider(Provider):
    @description("Lists available services")
    @query("service")
    def query(self, filter=None, params=None):
        ld = launchd.Launchd()

        def extend(i):
            label = i['launchd.Label']
            job = ld.jobs[label]
            state = 'RUNNING' if 'PID' in job else 'STOPPED'

            entry = {
                'name': i['name'],
                'state': state,
            }

            if 'PID' in job:
                entry['pid'] = job['PID']

            return entry

        return self.datastore.query('service-definitions', *(filter or []), callback=extend, **(params or {}))

    def get_service_config(self, service):
        svc = self.datastore.get_one('service-definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.EINVAL, 'Invalid service name')

        result = {}

        for i in svc['settings']:
            result.update(self.dispatcher.configstore.list_children(i))

        return result

    @private
    @accepts(str)
    def ensure_started(self, service):
        ld = launchd.Launchd()
        svc = self.datastore.get_one('service-definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.EINVAL, 'Invalid service name')

    @private
    @accepts(str)
    def ensure_stopped(self, service):
        ld = launchd.Launchd()
        svc = self.datastore.get_one('service-definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.EINVAL, 'Invalid service name')

    @private
    @accepts(str)
    def reload(self, service):
        ld = launchd.Launchd()
        svc = self.datastore.get_one('service-definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.EINVAL, 'Invalid service name')



@description("Provides functionality to start, stop, restart or reload service")
@accepts(
    str,
    h.enum(str, ['START', 'STOP', 'RESTART', 'RELOAD'])
)
class ServiceManageTask(Task):
    def describe(self, name, action):
        return "{0}ing service {1}".format(action.title(), name)

    def verify(self, name, action):
        if not self.datastore.exists('service-definitions', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Service {0} not found'.format(name))

        return ['system']

    def run(self, name, action):
        ld = launchd.Launchd()
        service = self.datastore.get_one('services', ('name', '=', name))
        label = service['launchd.Label']
        job = ld.jobs[label]

        if action == 'START':
            if 'PID' in job:
                raise TaskException(errno.EBUSY, 'Service already running')

            ld.start(label)

        if action == 'STOP':
            if 'PID' not in job:
                raise TaskException(errno.ENOENT, 'Service already stopped')

            ld.stop(label)

        if action == 'RESTART':
            if 'PID' not in job:
                raise TaskException(errno.ENOENT, 'Service already stopped')

            ld.stop(label)
            ld.start(label)

        if action == 'RELOAD':
            if 'PID' not in job:
                raise TaskException(errno.ENOENT, 'Service is not running')

            # Send SIGHUP
            os.kill(job['PID'], signal.SIGHUP)


class UpdateServiceConfigTask(Task):
    def describe(self, service, updated_fields):
        return "Updating configuration for service {0}".format(service)

    def verify(self, service, updated_fields):
        return ['system']

    def run(self, service, updated_fields):
        service_def = self.datastore.get_one('service-definitions', ('name', '=', service))
        for k, v in updated_fields.items():
            if k not in service_def['settings'].keys():
                raise TaskException(errno.EINVAL, 'Invalid setting {0}'.format(k))

            self.configstore.set(k, v)

        self.dispatcher.dispatch_event('service.changed', {
            'operation': 'update',
            'ids': [service_def['id']]
        })

        self.chain('service.manage', service, 'reload')


def spawn_gettys(dispatcher):
    ld = launchd.Launchd()
    count = dispatcher.configstore.get('system.vt_count')
    for i in range(0, count):
        vtype = 'freenas' if i == 0 else 'Pc'
        plist = template(GETTY_TEMPLATE, type=vtype, vt='ttyv{0}'.format(i))
        ld.load(plist)


def _init(dispatcher):
    dispatcher.register_schema_definition('service', {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'name': {'type': 'string'},
            'pid': {'type': 'integer'},
            'state': {
                'type': 'string',
                'enum': ['RUNNING', 'STOPPED', 'UNKNOWN']
            }
        }
    })

    dispatcher.register_task_handler("service.manage", ServiceManageTask)
    dispatcher.register_task_handler("service.configure", UpdateServiceConfigTask)
    dispatcher.register_provider("services", ServiceInfoProvider)

    ld = launchd.Launchd()
    for svc in dispatcher.datastore.query('service-definitions'):
        if 'launchd' not in svc:
            continue

        plist = svc['launchd']
        label = plist['Label']

        # Prepare sockets specification based on 'service.%s.listen' config value
        if svc.get('socket-server'):
            sockets = []
            listen = dispatcher.configstore.get('service.{0}.listen'.format(svc['name']))
            for i in listen:
                sockets.append({
                    'SockType': 'stream',
                    'SockFamily': i['protocol'],
                    'SockNodeName': i['address'],
                    'SockServiceName': i['port']
                })

            plist['Sockets'] = {'Listeners': sockets}


        ld.load(plist)
        if dispatcher.configstore.get('service.{0}.enable'.format(svc['name'])):
            ld.start(label)

        dispatcher.register_resource(Resource('service:{0}'.format(svc['name'])), parents=['system'])

    spawn_gettys(dispatcher)
