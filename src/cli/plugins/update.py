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


from namespace import (Namespace, ConfigNamespace, Command, IndexCommand,
                       description)
from output import output_msg
from descriptions import events
from utils import parse_query_args


@description("Prints current Update Train")
class CurrentTrainCommand(Command):
    def run(self, context, args, kwargs, opargs):
        output_msg(context.connection.call_sync('update.get_current_train'))


@description("Checks for New Updates")
class CheckNowCommand(Command):
    def run(self, context, args, kwargs, opargs):
        output_msg(context.connection.call_sync('update.check_now_for_updates'))


@description("Updates the system and reboot it")
class UpdateNowCommand(Command):
    def run(self, context, args, kwargs, opargs):
        output_msg("System going for an update now...")
        context.submit_task('update.update')


@description("Update namespace")
class UpdateNamespace(Namespace):
    def __init__(self, name, context):
        super(UpdateNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self),
            'current_train': CurrentTrainCommand(),
            # 'check_now': CheckNowCommand(),
            # uncmment above when freenas-pkgtools get updated by sef
            'update_now': UpdateNowCommand(),
        }


def _init(context):
    context.attach_namespace('/', UpdateNamespace('update', context))
