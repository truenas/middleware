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

from task import Provider, Task, VerifyException, TaskException
from dispatcher.rpc import description, returns


@description("Provides access to configuration store")
class ConfigProvider(Provider):
    def get(self, key):
        return self.dispatcher.configstore.get(key)

    def list(self, root):
        return self.dispatcher.configstore.list_children(root)


@description("Updates configuration settings")
class UpdateConfigTask(Task):
    def verify(self, settings):
        return ['system']

    def run(self, settings):
        for i in settings:
            self.configstore.set(i['key'], i['value'])

        self.dispatcher.dispatch_event('config.changed', {
            'operation': 'update',
            'ids': [settings.keys()]
        })


def _init(dispatcher):
    dispatcher.register_task_handler('config.update', UpdateConfigTask)
    dispatcher.register_provider('config', ConfigProvider)