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
import argparse
import shlex
import imp
import logging
import struct
import fcntl
import platform
import termios
import config
import json
import gettext
import getpass
import traceback
import signal
from descriptions import events, tasks
from namespace import Namespace, RootNamespace, Command
from output import output_lock, output_msg
from dispatcher.client import Client, ClientError
from commands import ExitCommand, PrintenvCommand, SetenvCommand


if platform.system() == 'Darwin':
    import gnureadline as readline
else:
    import readline


DEFAULT_CONFIGFILE = '/usr/local/etc/middleware.conf'
DEFAULT_RC = os.path.expanduser('~/.freenascli.conf')
t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


EVENT_MASKS = [
    'client.logged',
    'task.created',
    'task.updated',
    'service.stopped',
    'service.started',
    'volume.created',
]


class VariableStore(object):
    class Variable(object):
        def __init__(self, default, type, choices=None):
            self.default = default
            self.type = type
            self.choices = choices
            self.value = default

        def __str__(self):
            if self.type == int:
                return str(self.value)

            if self.type == bool:
                return 'true' if self.value else 'false'

            return self.value

        def set(self, value):
            try:
                if self.type == int:
                    value = int(value)
            except ValueError:
                raise

            if self.choices is not None and value not in self.choices:
                raise ValueError(_("Value not on the list of possible choices"))

            self.value = value

    def __init__(self):
        self.variables = {
            'output-format': self.Variable('ascii', str, ['ascii', 'json']),
            'datetime-format': self.Variable('natural', str),
            'language': self.Variable(os.getenv('LANG', 'C'), str),
            'prompt': self.Variable('{host}:{path}>', str),
            'timeout': self.Variable(10, int),
            'tasks-blocking': self.Variable(False, bool),
            'show-events': self.Variable(True, bool)
        }

    def load(self, filename):
        pass

    def save(self, filename):
        pass

    def get(self, name):
        return self.variables[name].value

    def get_all(self):
        for name, var in self.variables.items():
            yield (name, var.value)

    def get_all_printable(self):
        for name, var in self.variables.items():
            yield (name, str(var))

    def set(self, name, value):
        self.variables[name].set(value)


class Context(object):
    def __init__(self):
        self.hostname = None
        self.connection = Client()
        self.ml = None
        self.logger = logging.getLogger('cli')
        self.plugin_dirs = []
        self.plugins = {}
        self.variables = VariableStore()
        self.root_ns = RootNamespace('')
        self.event_masks = ['*']
        config.instance = self

    def start(self):
        self.discover_plugins()
        self.connect()

    def connect(self):
        self.connection.on_event(self.print_event)
        self.connection.on_error(self.connection_error)
        self.connection.connect(self.hostname)

    def read_config_file(self, file):
        try:
            f = open(file, 'r')
            data = json.load(f)
            f.close()
        except (IOError, ValueError):
            raise

        if 'cli' not in data:
            return

        if 'plugin-dirs' not in data['cli']:
            return

        if type(data['cli']['plugin-dirs']) != list:
            return

        self.plugin_dirs += data['cli']['plugin-dirs']

    def discover_plugins(self):
        for dir in self.plugin_dirs:
            self.logger.debug(_("Searching for plugins in %s"), dir)
            self.__discover_plugin_dir(dir)

    def login_plugins(self):
        for i in self.plugins.values():
            if hasattr(i, '_login'):
                i._login(self)

    def __discover_plugin_dir(self, dir):
        for i in glob.glob1(dir, "*.py"):
            self.__try_load_plugin(os.path.join(dir, i))

    def __try_load_plugin(self, path):
        if path in self.plugins:
            return

        self.logger.debug(_("Loading plugin from %s"), path)
        name, ext = os.path.splitext(os.path.basename(path))
        plugin = imp.load_source(name, path)

        if hasattr(plugin, '_init'):
            plugin._init(self)
            self.plugins[path] = plugin

    def __try_reconnect(self):
        pass

    def attach_namespace(self, path, ns):
        splitpath = path.split('/')
        ptr = self.root_ns

        for n in splitpath[1:-1]:
            if n not in ptr.namespaces().keys():
                self.logger.warn(_("Cannot attach to namespace %s"), path)
                return

            ptr = ptr.namespaces()[n]

        ptr.register_namespace(ns)

    def connection_error(self, event):
        if event == ClientError.CONNECTION_CLOSED:
            self.__try_reconnect()
            return

    def print_event(self, event, data):
        output_lock.acquire()
        self.ml.blank_readline()

        translation = events.translate(self, event, data)
        if translation:
            output_msg(translation)

        sys.stdout.flush()
        self.ml.restore_readline()
        output_lock.release()

    def submit_task(self, name, *args):
        tid = self.connection.call_sync('task.submit', name, args)

        #if self.variables.get('blocking'):

        return tid


class MainLoop(object):
    builtin_commands = {
        'exit': ExitCommand(),
        'setenv': SetenvCommand(),
        'printenv': PrintenvCommand()
    }

    def __init__(self, context):
        self.context = context
        self.root_path = [self.context.root_ns]
        self.path = self.root_path[:]
        self.namespaces = []
        self.connection = None

    def __get_prompt(self):
        variables = {
            'path': '/'.join([x.get_name() for x in self.path]),
            'host': self.context.hostname
        }
        return self.context.variables.get('prompt').format(**variables)

    def greet(self):
        print _("Welcome to FreeNAS CLI! Type '?' for help at any point.")
        print

    def cd(self, ns):
        if not self.cwd.on_leave():
            return

        self.path.append(ns)
        self.cwd.on_enter()

    def cd_up(self):
        if not self.cwd.on_leave():
            return

        del self.path[-1]
        self.cwd.on_enter()

    @property
    def cwd(self):
        return self.path[-1]

    def tokenize(self, line):
        args = []
        kwargs = {}
        tokens = shlex.split(line, posix=False)

        for t in tokens:
            if t[0] == '"' and t[-1] == '"':
                t = t[1:-1]
                args.append(t)
                continue

            if '=' in t:
                key, eq, value = t.partition('=')
                if value[0] == '"' and value[-1] == '"':
                    value = value[1:-1]

                kwargs[key] = value
                continue

            args.append(t)

        return args, kwargs

    def repl(self):
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self.complete)

        self.greet()

        while True:
            line = raw_input(self.__get_prompt()).strip()
            self.process(line)

    def process(self, line):
        if len(line) == 0:
            return

        if line[0] == '/':
            self.path = self.root_path[:]
            line = line[1:]

        if line == '..':
            if len(self.path) > 1:
                self.cd_up()
                return

        tokens, kwargs = self.tokenize(line)
        oldpath = self.path[:]

        while tokens:
            token = tokens.pop(0)
            nsfound = False
            cmdfound = False

            if token in self.builtin_commands.keys():
                self.builtin_commands[token].run(self.context, tokens, kwargs)
                break

            try:
                for ns in self.cwd.namespaces():
                    if token == ns.get_name():
                        self.cd(ns)
                        nsfound = True
                        break

                for name, cmd in self.cwd.commands().items():
                    if token == name:
                        output_lock.acquire()
                        cmd.run(self.context, tokens, kwargs)
                        cmdfound = True
                        output_lock.release()
                        break

            except Exception, err:
                print 'Error: {0}'.format(str(err))
                traceback.print_exc()
                break
            else:
                if not nsfound and not cmdfound:
                    print _("Command not found! Type \"?\" for help.")
                    break

                if cmdfound:
                    self.path = oldpath
                    break

    def get_relative_object(self, ns, tokens):
        ptr = ns
        while len(tokens) > 0:
            token = tokens.pop(0)

            if issubclass(type(ptr), Namespace):
                nss = ptr.namespaces()
                for ns in ptr.namespaces():
                    if ns.get_name() == token:
                        ptr = ns
                        break

                cmds = ptr.commands()
                if token in cmds:
                    return cmds[token]

                if token in self.builtin_commands:
                    return self.builtin_commands[token]

        return ptr

    def complete(self, text, state):
        tokens = shlex.split(readline.get_line_buffer(), posix=False)
        obj = self.get_relative_object(self.cwd, tokens)

        if issubclass(type(obj), Namespace):
            choices = [x.get_name() for x in obj.namespaces()] + obj.commands().keys() + self.builtin_commands.keys()
            choices = [i + ' ' for i in choices]

        elif issubclass(type(obj), Command):
            choices = obj.complete(self.context, tokens)

        else:
            choices = []

        options = [i for i in choices if i.startswith(text)]
        if state < len(options):
            return options[state]
        else:
            return None

    def sigint(self):
        pass

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
    parser.add_argument('hostname', metavar='HOSTNAME', nargs='?', default='127.0.0.1')
    parser.add_argument('-c', metavar='CONFIG', default=DEFAULT_CONFIGFILE)
    parser.add_argument('-e', metavar='COMMANDS')
    parser.add_argument('-l', metavar='LOGIN')
    parser.add_argument('-p', metavar='PASSWORD')
    parser.add_argument('-D', metavar='DEFINE', action='append')
    args = parser.parse_args()
    context = Context()
    context.hostname = args.hostname
    context.read_config_file(args.c)
    context.start()

    if args.l:
        context.connection.login_user(args.l, args.p)
        context.connection.subscribe_events(*EVENT_MASKS)
        context.login_plugins()
    elif args.l is None and args.p is None and args.hostname == '127.0.0.1':
        context.connection.login_user(getpass.getuser(), '')
        context.connection.subscribe_events(*EVENT_MASKS)
        context.login_plugins()

    ml = MainLoop(context)
    context.ml = ml

    if args.D:
        for i in args.D:
            name, value = i.split('=')
            context.variables.set(name, value)

    if args.e:
        ml.process(args.e)
        return

    ml.repl()


if __name__ == '__main__':
    main()