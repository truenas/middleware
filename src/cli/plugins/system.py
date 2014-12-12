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


from namespace import Namespace, Command, IndexCommand, description
from output import output_dict, output_table, format_datetime
from descriptions import events
from utils import parse_query_args


@description("Provides status information about the server")
class StatusCommand(Command):
    def run(self, context, args, kwargs):
        output_dict(context.connection.call_sync('management.status'))


@description("Logs in to the server")
class LoginCommand(Command):
    def run(self, context, args, kwargs):
        context.connection.login_user(args[0], args[1])
        context.connection.subscribe_events('*')
        context.login_plugins()


@description("Prints events history")
class EventsCommand(Command):
    def run(self, context, args, kwargs):
        items = context.connection.call_sync('event.query', *parse_query_args(args, kwargs))
        output_table(items, [
            ('Event name', lambda t: events.translate(context, t['name'], t['args'])),
            ('Occurred at', lambda t: format_datetime(t['timestamp']))
        ])

@description("System namespace")
class SystemNamespace(Namespace):
    def commands(self):
        return {
            '?': IndexCommand(self),
            'login': LoginCommand(),
            'status': StatusCommand(),
            'events': EventsCommand()
        }


def _init(context):
    context.attach_namespace('/', SystemNamespace('system'))