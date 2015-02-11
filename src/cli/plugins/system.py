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


import copy
from namespace import Namespace, ConfigNamespace, Command, IndexCommand, description
from output import Column, ValueType, output_dict, output_table, output_object
from descriptions import events
from utils import parse_query_args


@description("Provides status information about the server")
class StatusCommand(Command):
    def run(self, context, args, kwargs, opargs):
        output_dict(context.connection.call_sync('management.status'))


@description("Provides information about running system")
class InfoCommand(Command):
    def run(self, context, args, kwargs, opargs):
        pass


@description("Prints FreeNAS version information")
class VersionCommand(Command):
    def run(self, context, args, kwargs, opargs):
        output_object(
            ('FreeNAS version', 'freenas-version', context.connection.call_sync('system.info.version')),
            ('System version', 'system-version', context.connection.call_sync('system.info.uname_full'))
        )


@description("Logs in to the server")
class LoginCommand(Command):
    def run(self, context, args, kwargs, opargs):
        context.connection.login_user(args[0], args[1])
        context.connection.subscribe_events('*')
        context.login_plugins()


@description("Prints session history")
class SessionsCommand(Command):
    def run(self, context, args, kwargs, opargs):
        items = context.connection.call_sync('sessions.query', *parse_query_args(args, kwargs))
        output_table(items, [
            Column('Session ID', '/id', ValueType.NUMBER),
            Column('User name', '/user', ValueType.STRING),
            Column('Started at', '/started-at', ValueType.TIME),
            Column('Ended at', '/ended-at', ValueType.TIME)
        ])


@description("Prints event history")
class EventsCommand(Command):
    def run(self, context, args, kwargs, opargs):
        items = context.connection.call_sync('sessions.query', *parse_query_args(args, kwargs))
        output_table(items, [
            Column('Event name', lambda t: events.translate(context, t['name'], t['args'])),
            Column('Time', '/timestamp', ValueType.TIME)
        ])


@description("Time namespace")
class TimeNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(TimeNamespace, self).__init__(name, context)

        self.add_property(
            descr='System time',
            name='system_time',
            get='/system-time',
            list=True
        )

        self.add_property(
            descr='Bootup time',
            name='boot_time',
            get='/boot-time',
            set=None,
            list=True
        )

        self.add_property(
            descr='Time zone',
            name='timezone',
            get='/timezone',
            list=True
        )

    def load(self):
        self.entity = self.context.connection.call_sync('system.info.time')
        self.orig_entity = copy.deepcopy(self.entity)

    def save(self, entity, diff, new):
        self.context.submit_task('system.time.configure', diff)


@description("System namespace")
class SystemNamespace(Namespace):
    def __init__(self, name, context):
        super(SystemNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self),
            'login': LoginCommand(),
            'status': StatusCommand(),
            'version': VersionCommand(),
            'info': InfoCommand(),
            'events': EventsCommand(),
            'sessions': SessionsCommand()
        }

    def namespaces(self):
        return [
            TimeNamespace('time', self.context)
        ]


def _init(context):
    context.attach_namespace('/', SystemNamespace('system', context))