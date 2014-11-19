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
from texttable import Texttable


def description(descr):
    def wrapped(fn):
        fn.description = descr
        return fn

    return wrapped


class Namespace(object):
    def __init__(self):
        self.nslist = {}

    def help(self):
        pass

    def commands(self):
        return {
            '?': IndexCommand(self),
            'help': IndexCommand(self),
            'exit': ExitCommand()
        }

    def namespaces(self):
        return self.nslist

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def register_namespace(self, name, ns):
        self.nslist[name] = ns


class Command(object):
    def run(self, context, args):
        pass


@description("Provides list of commands in this namespace")
class IndexCommand(Command):
    def __init__(self, target):
        self.target = target

    def run(self, context, args):
        table = Texttable()
        table.set_deco(Texttable.HEADER | Texttable.VLINES | Texttable.BORDER)
        table.add_rows([['Command', 'Description']], header=True)
        nss = self.target.namespaces()
        cmds = self.target.commands()

        for name in sorted(nss.keys()):
            table.add_row([name, nss[name].description])

        for name in sorted(cmds.keys()):
            table.add_row([name, cmds[name].description])

        print table.draw()


@description("Exits the CLI")
class ExitCommand(Command):
    def run(self, context, args):
        sys.exit(0)


class RootNamespace(Namespace):
    pass