#!/usr/bin/env python
# +
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
import errno
import struct
import fcntl
import platform
import termios
import config
import json
import time
import gettext
import getpass
import traceback
import Queue
import threading
from descriptions import events
from namespace import Namespace, RootNamespace, Command
from output import (
    ValueType, ProgressBar, output_lock, output_msg, read_value, format_value,
    output_list
)
from dispatcher.client import Client, ClientError
from dispatcher.rpc import RpcException
from fnutils.query import wrap
from commands import (
    ExitCommand, PrintenvCommand, SetenvCommand, ShellCommand, ShutdownCommand,
    RebootCommand, EvalCommand, HelpCommand, ShowUrlsCommand, ShowIpsCommand
)

if platform.system() == 'Darwin':
    import gnureadline as readline
else:
    import readline


DEFAULT_CONFIGFILE = '/usr/local/etc/middleware.conf'
DEFAULT_RC = os.path.expanduser('~/.freenascli.conf')
t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


PROGRESS_CHARS = ['-', '\\', '|', '/']
OPERATORS = ['<=', '>=', '!=', '+=', '-=', '~=', '=', '<', '>']
EVENT_MASKS = [
    'client.logged',
    'task.created',
    'task.updated',
    'task.progress',
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

        def set(self, value):
            value = read_value(value, self.type)
            if self.choices is not None and value not in self.choices:
                raise ValueError(_("Value not on the list of possible choices"))

            self.value = value

        def __str__(self):
            return format_value(self.value, self.type)

    def __init__(self):
        self.variables = {
            'output-format': self.Variable('ascii', ValueType.STRING, ['ascii', 'json', 'table']),
            'datetime-format': self.Variable('natural', ValueType.STRING),
            'language': self.Variable(os.getenv('LANG', 'C'), ValueType.STRING),
            'prompt': self.Variable('{host}:{path}>', ValueType.STRING),
            'timeout': self.Variable(10, ValueType.NUMBER),
            'tasks-blocking': self.Variable(False, ValueType.BOOLEAN),
            'show-events': self.Variable(True, ValueType.BOOLEAN),
            'debug': self.Variable(False, ValueType.BOOLEAN)
        }

    def load(self, filename):
        pass

    def save(self, filename):
        pass

    def get(self, name):
        return self.variables[name].value

    def get_all(self):
        return self.variables.items()

    def get_all_printable(self):
        for name, var in self.variables.items():
            yield (name, str(var))

    def set(self, name, value):
        if name not in self.variables:
            self.variables[name] = self.Variable('', ValueType.STRING)

        self.variables[name].set(value)


class Context(object):
    def __init__(self):
        self.hostname = None
        self.connection = Client()
        self.ml = None
        self.logger = logging.getLogger('cli')
        self.plugin_dirs = []
        self.task_callbacks = {}
        self.plugins = {}
        self.variables = VariableStore()
        self.root_ns = RootNamespace('')
        self.event_masks = ['*']
        self.event_divert = False
        self.event_queue = Queue.Queue()
        self.keepalive_timer = None
        config.instance = self

    def start(self):
        self.discover_plugins()
        self.connect()

    def connect(self):
        self.connection.connect(self.hostname)

    def login(self, user, password):
        try:
            self.connection.login_user(user, password)
            self.connection.subscribe_events(*EVENT_MASKS)
            self.connection.on_event(self.handle_event)
            self.connection.on_error(self.connection_error)

        except RpcException, e:
            if e.code == errno.EACCES:
                self.connection.disconnect()
                output_msg(_("Wrong username od password"))
                sys.exit(1)

        self.login_plugins()

    def keepalive(self):
        if self.connection.opened:
            self.connection.call_sync('management.ping')

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
        output_lock.acquire()
        self.ml.blank_readline()

        output_msg('Connection lost! Trying to reconnect...')
        retries = 0
        while True:
            retries += 1
            try:
                time.sleep(5)
                self.connect()
                try:
                    self.connection.login_token(self.connection.token)
                    self.connection.subscribe_events(*EVENT_MASKS)
                except RpcException:
                    output_msg('Reauthentication using token failed (most likely token expired or server was restarted)')
                    sys.exit(1)
                break
            except Exception, e:
                output_msg('Cannot reconnect: {0}'.format(str(e)))

        self.ml.restore_readline()
        output_lock.release()

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
        if event == ClientError.LOGOUT:
            output_msg('Logged out from server.')
            self.connection.disconnect()
            sys.exit(0)

        if event == ClientError.CONNECTION_CLOSED:
            time.sleep(1)
            self.__try_reconnect()
            return

    def handle_event(self, event, data):
        if event == 'task.updated':
            if data['id'] in self.task_callbacks:
                self.handle_task_callback(data)

        self.print_event(event, data)

    def handle_task_callback(self, data):
        if data['state'] in ('FINISHED', 'CANCELED', 'ABORTED'):
            self.task_callbacks[data['id']](data['state'])

    def print_event(self, event, data):
        if self.event_divert:
            self.event_queue.put((event, data))
            return

        if event == 'task.progress':
            return

        output_lock.acquire()
        self.ml.blank_readline()

        translation = events.translate(self, event, data)
        if translation:
            output_msg(translation)

        sys.stdout.flush()
        self.ml.restore_readline()
        output_lock.release()

    def call_sync(self, name, *args, **kwargs):
        return wrap(self.connection.call_sync(name, *args, **kwargs))

    def submit_task(self, name, *args, **kwargs):
        callback = kwargs.pop('callback', None)

        if not self.variables.get('tasks-blocking'):
            tid = self.connection.call_sync('task.submit', name, args)
            if callback:
                self.task_callbacks[tid] = callback

            return tid
        else:
            self.event_divert = True
            tid = self.connection.call_sync('task.submit', name, args)
            progress = ProgressBar()
            while True:
                event, data = self.event_queue.get()

                if event == 'task.progress' and data['id'] == tid:
                    progress.update(percentage=data['percentage'],
                                    message=data['message'])

                if event == 'task.updated' and data['id'] == tid:
                    progress.update(message=data['state'])
                    if data['state'] == 'FINISHED':
                        progress.finish()
                        break

        self.event_divert = False
        return tid


class MainLoop(object):
    builtin_commands = {
        'exit': ExitCommand(),
        'setenv': SetenvCommand(),
        'printenv': PrintenvCommand(),
        'shell': ShellCommand(),
        'eval': EvalCommand(),
        'shutdown': ShutdownCommand(),
        'reboot': RebootCommand(),
        'help': HelpCommand(),
        'showips': ShowIpsCommand(),
        'showurls': ShowUrlsCommand()
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
        opargs = []
        kwargs = {}
        tokens = shlex.split(line, posix=False)

        for t in tokens:
            found = False

            if t[0] == '"' and t[-1] == '"':
                t = t[1:-1]
                args.append(t)
                continue

            for op in OPERATORS:
                if op in t:
                    key, eq, value = t.partition(op)
                    if value[0] == '"' and value[-1] == '"':
                        value = value[1:-1]

                    if op == '=':
                        kwargs[key] = value
                        found = True
                        break

                    opargs.append((key, op, value))
                    found = True
                    break

            if not found:
                args.append(t)

        return args, kwargs, opargs

    def repl(self):
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self.complete)

        self.greet()
        a = ShowUrlsCommand()
        a.run(self.context, None, None, None)

        while True:
            try:
                line = raw_input(self.__get_prompt()).strip()
            except EOFError:
                print
                return

            self.process(line)

    def process(self, line):
        if len(line) == 0:
            return

        if line[0] == '!':
            self.builtin_commands['shell'].run(
                self.context, [line[1:]], {}, {})
            return

        if line[0] == '/':
            self.path = self.root_path[:]
            line = line[1:]

        if line == '..':
            if len(self.path) > 1:
                self.cd_up()
                return

        tokens, kwargs, opargs = self.tokenize(line)
        oldpath = self.path[:]

        while tokens:
            token = tokens.pop(0)
            nsfound = False
            cmdfound = False

            try:
                if token in self.builtin_commands.keys():
                    self.builtin_commands[token].run(
                        self.context, tokens, kwargs, opargs)
                    break

                for ns in self.cwd.namespaces():
                    if token == ns.get_name():
                        self.cd(ns)
                        nsfound = True
                        break

                for name, cmd in self.cwd.commands().items():
                    if token == name:
                        output_lock.acquire()
                        try:
                            cmd.run(self.context, tokens, kwargs, opargs)
                        except Exception, e:
                            output_msg(
                                'Command {0} failed: {1}'.format(name, str(e)))
                            if self.context.variables.get('debug'):
                                traceback.print_exc()

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
                for ns in nss:
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
            choices = [x.get_name() for x in obj.namespaces()] + \
                obj.commands().keys() + \
                self.builtin_commands.keys()
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
        rows, cols = struct.unpack('hh', fcntl.ioctl(
            sys.stdout, termios.TIOCGWINSZ, '1234'))

        if cols == 0:
            cols = 80

        text_len = len(readline.get_line_buffer()) + 2
        sys.stdout.write('\x1b[2K')
        sys.stdout.write('\x1b[1A\x1b[2K' * (text_len / cols))
        sys.stdout.write('\x1b[0G')

    def restore_readline(self):
        sys.stdout.write(self.__get_prompt() + readline.get_line_buffer().rstrip())
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('hostname', metavar='HOSTNAME', nargs='?',
                        default='127.0.0.1')
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

    ml = MainLoop(context)
    context.ml = ml

    if args.l:
        context.login(args.l, args.p)
    elif args.l is None and args.p is None and args.hostname == '127.0.0.1':
        context.login(getpass.getuser(), '')

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
