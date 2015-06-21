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
import inspect
import termios
import sys
import select
import sandbox
import gettext
from namespace import Command, CommandException, description
from output import (
    Column, output_value, output_dict, format_value, output_msg, output_list
)
from dispatcher.shell import ShellClient

t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


@description("Sets variable value")
class SetenvCommand(Command):
    """
    Usage: setenv <variable> <value>

    Sets value of environment variable.
    """
    def run(self, context, args, kwargs, opargs):
        if len(args) < 2:
            raise CommandException('Wrong parameter count')

        context.variables.set(args[0], args[1])

    def complete(self, context, tokens):
        return [k for k, foo in context.variables.get_all()]


@description("Evaluates Python code")
class EvalCommand(Command):
    """
    Usage: eval <Python code fragment>

    Examples:
        eval "print 'hello world'"
    """
    def run(self, context, args, kwargs, opargs):
        sandbox.evaluate(args[0])


@description("Spawns shell, enter \"!shell\" (example: \"!sh\")")
class ShellCommand(Command):
    """
    Usage: shell [command]

    Launches interactive shell on FreeNAS host. That means if CLI is
    used to connect to remote host, also remote shell will be used.
    By default, launches current (logged in) user's login shell. Optional
    positional argument may specify alternative command to run.
    """
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
        name = args[0] if len(args) > 0 and len(args[0]) > 0 else '/bin/sh'
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
    """
    Usage: printenv [variable]

    Prints a list of environment variables and their values (if called without
    arguments) or value of single environment variable (if called with single
    positional argument - variable name)
    """
    def run(self, context, args, kwargs, opargs):
        if len(args) == 0:
            output_dict(dict(context.variables.get_all_printable()))

        if len(args) == 1:
            output_value(context.variables.get(args[0]))
            return


@description("Shuts the system down")
class ShutdownCommand(Command):
    """
    Usage: shutdown
    """
    def run(self, context, args, kwargs, opargs):
        output_msg(_("System going for a shutdown..."))
        context.submit_task('system.shutdown')


@description("Reboots the system")
class RebootCommand(Command):
    """
    Usage: reboot
    """
    def run(self, context, args, kwargs, opargs):
        output_msg(_("System going for a reboot..."))
        context.submit_task('system.reboot')


@description("Displays the active ips from all configured network interface")
class ShowIpsCommand(Command):
    """
    Usage: showips
    """
    def run(self, context, args, kwargs, opargs):
        output_msg(_("These are the active ips from all the configured"
                     " network interfaces"))
        output_list(context.connection.call_sync('network.config.get_my_ips'),
                    _("IP Addresses"))


@description("Displays the URLs to access the web GUI from")
class ShowUrlsCommand(Command):
    """
    Usage: showips
    """
    def run(self, context, args, kwargs, opargs):
        output_msg(_("You may try the following URLs to access"
                     " the web user interface:"))
        my_ips = context.connection.call_sync('network.config.get_my_ips')
        my_protocols = context.connection.call_sync(
            'system.ui.get_config')
        urls = []
        for proto in my_protocols['webui-procotol']:
            proto_port = my_protocols['webui-{0}-port'.format(proto.lower())]
            if proto_port is not None:
                if proto_port in [80, 443]:
                    for x in my_ips:
                        urls.append('{0}://{1}'.format(proto.lower(), x))
                else:
                    for x in my_ips:
                        urls.append('{0}://{1}:{2}'.format(proto.lower(), x,
                                                           proto_port))
        output_list(urls, label=_('URLs'))


@description("Exits the CLI, enter \"^D\" (ctrl+D)")
class ExitCommand(Command):
    """
    Usage: exit
    """
    def run(self, context, args, kwargs, opargs):
        sys.exit(0)


@description("Provides help on commands")
class HelpCommand(Command):
    """
    Usage: help [command command ...]

    Provides usage information on particular command. If command can't be
    reached directly in current namespace, may be specified as chain,
    eg: "account users show".

    Examples:
        help
        help printenv
        help account users show
    """
    def run(self, context, args, kwargs, opargs):
        obj = context.ml.get_relative_object(context.ml.path[-1], args)

        if obj.__doc__:
            output_msg(inspect.getdoc(obj))
