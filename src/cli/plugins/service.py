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


from namespace import Namespace, EntityNamespace, RpcBasedLoadMixin, Command, description


class ServiceManageCommand(Command):
    def __init__(self, parent, action):
        self.parent = parent
        self.action = action

    @property
    def description(self):
        return '{0}s service'.format(self.action.title())

    def run(self, context, args, kwargs, opargs):
        context.submit_task('service.manage', self.parent.primary_key, self.action)


@description("Service namespace")
class ServicesNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(ServicesNamespace, self).__init__(name, context)
        self.query_call = 'services.query'

        self.add_property(
            descr='Service name',
            name='name',
            get='/name',
            set=None,
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get='/state',
            set=None,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.allow_edit = False
        self.allow_creation = False
        self.entity_commands = lambda this: {
            'start': ServiceManageCommand(this, 'start'),
            'stop': ServiceManageCommand(this, 'stop'),
            'restart': ServiceManageCommand(this, 'restart'),
            'reload': ServiceManageCommand(this, 'reload')
        }


class ServiceConfigNamespace(Namespace):
    pass


def _init(context):
    context.attach_namespace('/', ServicesNamespace('services', context))