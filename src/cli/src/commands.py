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
import tty
import termios
import sys
import select
from namespace import Command, CommandException, description
from output import Column, ValueType, output_value, output_table, format_value
from dispatcher.shell import ShellClient


@description("Sets variable value")
class SetenvCommand(Command):
    def run(self, context, args, kwargs, opargs):
        if len(args) < 2:
            raise CommandException('Wrong parameter count')

        context.variables.set(args[0], args[1])

    def complete(self, context, tokens):
        return [k for k, _ in context.variables.get_all()]


@description("Evaluates Python code")
class EvalCommand(Command):
    def run(self, context, args, kwargs, opargs):
        pass

@description("Spawns shell")
class ShellCommand(Command):
    def __init__(self):
        super(ShellCommand, self).__init__()
        self.closed = False

    def run(self, context, args, kwargs, opargs):
        def read(data):
            sys.stdout.write(data)
            sys.stdout.flush()

        def close():
            self.closed = True

        self.closed = False
        name = args[0] if len(args) > 0 else '/bin/sh'
        token = context.connection.call_sync('shell.spawn', name)
        shell = ShellClient(context.hostname, token)
        shell.open()
        shell.on_data(read)
        shell.on_close(close)

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)

        while not self.closed:
            r, w, x = select.select([fd], [], [], 0.1)
            if fd in r:
                ch = os.read(fd, 1)
                shell.write(ch)

        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)



@description("Prints variable value")
class PrintenvCommand(Command):
    def run(self, context, args, kwargs, opargs):
        if len(args) == 0:
            output_table(context.variables.get_all(), [
                Column('Name', lambda (name, var): name),
                Column('Value', lambda (name, var): format_value(var.value, var.type))
            ])
            return

        if len(args) == 1:
            output_value(context.variables.get(args[0]))
            return


@description("Exits the CLI")
class ExitCommand(Command):
    def run(self, context, args, kwargs, opargs):
        sys.exit(0)