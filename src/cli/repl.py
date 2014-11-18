#!/usr/bin/env python
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
import os
import glob
import gnureadline as readline
import argparse
import imp
import logging
import struct
import fcntl
import termios
from namespace import RootNamespace
from dispatcher.client import Client


class Context(object):
    def __init__(self):
        self.hostname = None
        self.connection = None
        self.ml = None
        self.logger = logging.getLogger('cli')
        self.plugin_dirs = []
        self.plugins = {}
        self.root_ns = RootNamespace()
        self.event_masks = ['*']

    def start(self):
        self.discover_plugins()
        self.connect()

    def connect(self):
        self.connection = Client()
        self.connection.on_event(self.print_event)
        self.connection.connect(self.hostname)

    def discover_plugins(self):
        for dir in self.plugin_dirs:
            self.logger.debug("Searching for plugins in %s", dir)
            self.__discover_plugin_dir(dir)

    def __discover_plugin_dir(self, dir):
        for i in glob.glob1(dir, "*.py"):
            self.__try_load_plugin(os.path.join(dir, i))

    def __try_load_plugin(self, path):
        if path in self.plugins:
            return

        self.logger.debug("Loading plugin from %s", path)
        plugin = imp.load_source('plugin', path)
        if hasattr(plugin, '_init'):
            plugin._init(self)
            self.plugins[path] = plugin

    def attach_namespace(self, path, ns):
        splitpath = path.split('/')
        ptr = self.root_ns

        for n in splitpath[1:-1]:
            if n not in ptr.namespaces().keys():
                self.logger.warn('Cannot attach to namespace %s', path)
                return

            ptr = ptr.namespaces()[n]

        ptr.register_namespace(splitpath[-1], ns)

    def print_event(self, event, data):
        self.ml.blank_readline()
        print 'Event: {0}'.format(data['description'])
        self.ml.restore_readline()


class PathItem(object):
    def __init__(self, name, ns):
        self.name = name
        self.ns = ns


class MainLoop(object):
    def __init__(self, context):
        self.context = context
        self.path = [PathItem(self.context.hostname, self.context.root_ns)]
        self.namespaces = []
        self.connection = None

    def __get_prompt(self):
        return '/'.join([x.name for x in self.path]) + '> '

    def cd(self, name, ns):
        self.path.append(PathItem(name, ns))

    @property
    def cwd(self):
        return self.path[-1]

    def repl(self):
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self.complete)
        while True:
            line = raw_input(self.__get_prompt()).strip()

            if len(line.strip()) == 0:
                continue

            if line == '..':
                if len(self.path) > 1:
                    del self.path[-1]
                    continue

            tokens = line.split()
            found = False

            for token in tokens:
                for name, ns in self.cwd.ns.namespaces().items():
                    if token == name:
                        self.cd(token, ns)
                        found = True
                        break

                for name, cmd in self.cwd.ns.commands().items():
                    if token == name:
                        cmd.run(self.context, tokens)
                        found = True
                        break

            if not found:
                print 'Command not found! Type "?" for help.'

    def complete(self, text, state):
        #self.blank_readline()
        #self.cwd.ns.commands()['?'].run(self.context, [])
        #self.restore_readline()
        choices = self.cwd.ns.namespaces().keys() + self.cwd.ns.commands().keys()
        options = [i for i in choices if i.startswith(text)]
        if state < len(options):
            return options[state]
        else:
            return None

    def blank_readline(self):
        rows, cols = struct.unpack('hh', fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, '1234'))
        text_len = len(readline.get_line_buffer()) + 2
        sys.stdout.write('\x1b[2K')
        sys.stdout.write('\x1b[1A\x1b[2K' * (text_len / cols))
        sys.stdout.write('\x1b[0G')

    def restore_readline(self):
        sys.stdout.write(self.__get_prompt() + readline.get_line_buffer().rstrip())
        sys.stdout.flush()


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('hostname', metavar='HOSTNAME', default='127.0.0.1')
    parser.add_argument('-I', metavar='DIR')
    args = parser.parse_args()
    context = Context()
    context.hostname = args.hostname
    context.plugin_dirs = [args.I]
    context.start()
    ml = MainLoop(context)
    context.ml = ml
    ml.repl()


if __name__ == '__main__':
    main()