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


import time
from descriptions import tasks
from namespace import Namespace, IndexCommand, Command, description
from output import output_msg, output_table, format_datetime


@description("Lists system services")
class ListCommand(Command):
    def run(self, context, args, kwargs):
        self.context = context
        tasks = context.connection.call_sync('task.query')
        output_table(tasks, [
            ('ID', '/id'),
            ('Started at', lambda t: format_datetime(t['started_at'])),
            ('Finished at', lambda t: format_datetime(t['finished_at'])),
            ('Description', self.describe_task),
            ('State', self.describe_state)
        ])

    def describe_state(self, task):
        if task['state'] == 'EXECUTING':
            state = self.context.connection.call_sync('task.status', task['id'])
            if 'progress' not in state:
                return task['state']

            return '{0:2.0f}% ({1})'.format(state['progress']['percentage'], state['progress']['message'])

        return task['state']

    def describe_task(self, task):
        return tasks.translate(self.context, task['name'], task['args'])


@description("Submits new task")
class SubmitCommand(Command):
    def run(self, context, args, kwargs):
        name = args.pop(0)
        tid = context.connection.call_sync('task.submit', name, args)
        output_msg('Task {0} started'.format(tid))


@description("Service namespace")
class TasksNamespace(Namespace):
    def __init__(self, name, context):
        super(TasksNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self),
            'list': ListCommand(),
            'submit': SubmitCommand()
        }


def _init(context):
    context.attach_namespace('/', TasksNamespace('tasks', context))