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

import sys
from namespace import Command, CommandException, description
from output import output_value, output_dict


@description("Sets variable value")
class SetenvCommand(Command):
    def run(self, context, args, kwargs):
        if len(args) < 2:
            raise CommandException('Wrong parameter count')

        context.variables.set(args[0], args[1])

    def complete(self, context, tokens):
        return [k for k, _ in context.variables.get_all()]

@description("Prints variable value")
class PrintenvCommand(Command):
    def run(self, context, args, kwargs):
        if len(args) == 0:
            output_dict({k: v for k, v in context.variables.get_all_printable()}, key_label='Variable name', value_label='Value')
            return

        if len(args) == 1:
            output_value(context.variables.get(args[0]))
            return


@description("Exits the CLI")
class ExitCommand(Command):
    def run(self, context, args, kwargs):
        sys.exit(0)