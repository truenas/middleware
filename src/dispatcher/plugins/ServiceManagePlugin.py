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
from dispatcher.rpc import RpcException, description, accepts, returns, private
from balancer import TaskState
from event import EventSource
from lib.system import system, SubprocessException


@description("Provides info about available services and their state")
class ServiceInfoProvider(Provider):
    def initialize(self, context):
        self.datastore = context.dispatcher.datastore

    @description("Lists available services")
    @returns({
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'id': {'type': 'string'},
                'name': {'type': 'string'},
                'pid': {'type': 'integer'},
                'state': {
                    'type': 'string',
                    'enum': ['running', 'stopped', 'unknown']
                }
            }
        }
    })
    def query(self, filter=None, params=None):
        result = []
        filter = filter if filter else []
        params = params if params else {}

        for i in self.datastore.query('service_definitions', *filter, **params):

            if 'pidfile' in i:
                # Check if process is alive by reading pidfile
                try:
                    fd = open(i['pidfile'], 'r')
                    pid = int(fd.read().strip())
                except IOError:
                    pid = None
                    state = 'stopped'
                except ValueError:
                    pid = None
                    state = 'stopped'
                else:
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        state = 'unknown'
                    else:
                        state = 'running'
            else:
                # Fallback to 'service xxx status'
                pid = None
                state = 'unknown'

            entry = {
                'name': i['name'],
                'state': state,
            }

            if pid is not None:
                entry['pid'] = pid

            result.append(entry)

        return result

    def get_service_config(self, service):
        svc = self.dispatcher.get_one('service_definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.EINVAL, 'Invalid service name')

        result = {}

        for i in svc['settings']:
            result.update(self.dispatcher.configstore.list_children(i))

        return result

    @private
    def ensure_started(self, service):
        # XXX launchd!
        try:
            system("/usr/sbin/service", service, "onestart")
        except SubprocessException, e:
            pass

    @private
    def ensure_stopped(self, service):
        # XXX launchd!
        try:
            system("/usr/sbin/service", service, "onestop")
        except SubprocessException, e:
            pass

    @private
    def reload(self, service):
        # XXX launchd!
        try:
            system("/usr/sbin/service", service, "onereload")
        except SubprocessException, e:
            pass


@description("Provides functionality to start, stop, restart or reload service")
@accepts({
    'title': 'name',
    'type': 'string'
}, {
    'title': 'action',
    'type': 'string',
    'enum': ['start', 'stop', 'restart', 'reload']
})
class ServiceManageTask(Task):
    def describe(self, name, action):
        return "{0}ing service {1}".format(action.title(), name)

    def verify(self, name, action):
        if action not in ('start', 'stop', 'restart', 'reload'):
            raise TaskException(errno.EINVAL, "Invalid action")

        try:
            out, err = system("/usr/sbin/service", "-l")
        except SubprocessException, e:
            raise TaskException(errno.ENXIO, e.err)

        if name not in out.split():
            raise TaskException(errno.ENOENT, "No such service")

        return ['system']

    def run(self, name, action):
        try:
            system("/usr/sbin/service", name, action)
        except SubprocessException, e:
            raise TaskException(errno.EBUSY, e.err)


class UpdateServiceConfigTask(Task):
    def describe(self, service, updated_fields):
        return "Updating configuration for service {0}".format(service)

    def verify(self, service, updated_fields):
        return ['system']

    def run(self, service, updated_fields):
        service_def = self.datastore.get_one('service_definitions', ('name', '=', service))
        for k, v in updated_fields.items():
            if k not in service_def['settings'].keys():
                raise TaskException(errno.EINVAL, 'Invalid setting {0}'.format(k))

            self.configstore.set(k, v)

        self.dispatcher.dispatch_event('service.changed', {
            'operation': 'update',
            'ids': [service_def['id']]
        })

        self.chain('service.manage', service, 'reload')


def _init(dispatcher):
    def on_rc_command(args):
        cmd = args['action']
        name = args['name']
        svc = dispatcher.datastore.get_one('service_definitions', ('service-name', '=', name))

        if svc is None:
            # ignore unknown rc scripts
            return

        if cmd not in ('start', 'stop', 'reload', 'restart'):
            # ignore unknown actions
            return

        if cmd == 'stop':
            cmd += 'p'

        dispatcher.dispatch_event('service.{0}ed'.format(cmd), {
            'name': svc['name']
        })

    dispatcher.register_event_handler("service.rc.command", on_rc_command)
    dispatcher.register_task_handler("service.manage", ServiceManageTask)
    dispatcher.register_task_handler("service.configure", UpdateServiceConfigTask)
    dispatcher.register_provider("service", ServiceInfoProvider)