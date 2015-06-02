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
from task import Task, Provider, TaskException, VerifyException, query
from resources import Resource
from dispatcher.rpc import RpcException, description, accepts, private
from dispatcher.rpc import SchemaHelper as h
from datastore.config import ConfigNode
from lib.system import system, SubprocessException


@description("Provides info about available services and their state")
class ServiceInfoProvider(Provider):
    @description("Lists available services")
    @query("service")
    def query(self, filter=None, params=None):
        def extend(i):
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
            elif 'rcng' in i and 'rc-scripts' in i['rcng']:
                rc_scripts = i['rcng']['rc-scripts']
                pid = None
                state = 'running'
                try:
                    if type(rc_scripts) is unicode:
                        system("/usr/sbin/service", rc_scripts, 'onestatus')

                    if type(rc_scripts) is list:
                        for x in rc_scripts:
                            system("/usr/sbin/service", x, 'onestatus')
                except SubprocessException:
                    state = 'stopped'
            else:
                pid = None
                state = 'unknown'

            entry = {
                'name': i['name'],
                'state': state,
            }

            if pid is not None:
                entry['pid'] = pid

            return entry

        return self.datastore.query('service_definitions', *(filter or []), callback=extend, **(params or {}))

    def get_service_config(self, service):
        svc = self.datastore.get_one('service_definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.EINVAL, 'Invalid service name')

        node = ConfigNode('service.{0}'.format(service), self.configstore)
        return node

    @private
    @accepts(str)
    def ensure_started(self, service):
        # XXX launchd!
        svc = self.datastore.get_one('service_definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.ENOENT, 'Service {0} not found'.format(service))

        rc_scripts = svc['rcng']['rc-scripts']

        try:
            if type(rc_scripts) is unicode:
                system("/usr/sbin/service", rc_scripts, 'onestart')

            if type(rc_scripts) is list:
                for i in rc_scripts:
                    system("/usr/sbin/service", i, 'onestart')
        except SubprocessException, e:
            pass

    @private
    @accepts(str)
    def ensure_stopped(self, service):
        # XXX launchd!
        svc = self.datastore.get_one('service_definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.ENOENT, 'Service {0} not found'.format(service))

        rc_scripts = svc['rcng']['rc-scripts']

        try:
            if type(rc_scripts) is unicode:
                system("/usr/sbin/service", rc_scripts, 'onestop')

            if type(rc_scripts) is list:
                for i in rc_scripts:
                    system("/usr/sbin/service", i, 'onestop')
        except SubprocessException, e:
            pass

    @private
    @accepts(str)
    def reload(self, service):
        svc = self.datastore.get_one('service_definitions', ('name', '=', service))
        if not svc:
            raise RpcException(errno.ENOENT, 'Service {0} not found'.format(service))

        rc_scripts = svc['rcng']['rc-scripts']
        self.ensure_started(service)

        try:
            if type(rc_scripts) is unicode:
                system("/usr/sbin/service", rc_scripts, 'onereload')

            if type(rc_scripts) is list:
                for i in rc_scripts:
                    system("/usr/sbin/service", i, 'onereload')
        except SubprocessException, e:
            pass


@description("Provides functionality to start, stop, restart or reload service")
@accepts(
    str,
    h.enum(str, ['start', 'stop', 'restart', 'reload'])
)
class ServiceManageTask(Task):
    def describe(self, name, action):
        return "{0}ing service {1}".format(action.title(), name)

    def verify(self, name, action):
        if not self.datastore.exists('service_definitions', ('name', '=', name)):
            raise VerifyException(errno.ENOENT, 'Service {0} not found'.format(name))

        return ['system']

    def run(self, name, action):
        service = self.datastore.get_one('service_definitions', ('name', '=', name))
        rc_scripts = service['rcng'].get('rc-scripts')
        try:
            if type(rc_scripts) is unicode:
                system("/usr/sbin/service", rc_scripts, 'one' + action)

            if type(rc_scripts) is list:
                for i in rc_scripts:
                    system("/usr/sbin/service", i, 'one' + action)

        except SubprocessException, e:
            raise TaskException(errno.EBUSY, e.err)


class UpdateServiceConfigTask(Task):
    def describe(self, service, updated_fields):
        return "Updating configuration for service {0}".format(service)

    def verify(self, service, updated_fields):
        return ['system']

    def run(self, service, updated_fields):
        service_def = self.datastore.get_one('service_definitions', ('name', '=', service))
        node = ConfigNode('service.{0}'.format(service), self.dispatcher.configstore)
        node.update(updated_fields)

        self.dispatcher.dispatch_event('service.changed', {
            'operation': 'update',
            'ids': [service_def['id']]
        })


def _init(dispatcher, plugin):
    def on_rc_command(args):
        cmd = args['action']
        name = args['name']
        svc = dispatcher.datastore.get_one('service_definitions', ('rc-scripts', '=', name))

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

    plugin.register_schema_definition('service', {
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
    })

    plugin.register_event_handler("service.rc.command", on_rc_command)
    plugin.register_task_handler("service.manage", ServiceManageTask)
    plugin.register_task_handler("service.configure", UpdateServiceConfigTask)
    plugin.register_provider("services", ServiceInfoProvider)

    for svc in dispatcher.datastore.query('service_defintions'):
        plugin.register_resource(Resource('service:{0}'.format(svc['name'])), parents=['system'])
