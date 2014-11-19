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

from namespace import Namespace, Command, IndexCommand
from utils import print_set


class AutoNamespace(Namespace):
    def __init__(self, context, service):
        super(AutoNamespace, self).__init__()
        self.context = context
        self.service = service
        self.description = '???'

    def commands(self):
        result = {'?': IndexCommand(self)}
        methods = self.context.connection.call_sync('discovery.get_methods', self.service)

        for m in methods:
            result[m['name']] = AutoCommand(self.service + '.' + m['name'], m['params-schema'], m['result-schema'])

        return result


class AutoCommand(Namespace):
    def __init__(self, path, params_schema, result_schema):
        super(AutoCommand, self).__init__()
        self.path = path
        self.params_schema = params_schema
        self.result_schema = result_schema
        self.description = '???'


    def run(self, context, args):
        result = context.connection.call_sync(self.path, *args)
        print_set(result)


def _init(context):
    pass


def _login(context):
    pass