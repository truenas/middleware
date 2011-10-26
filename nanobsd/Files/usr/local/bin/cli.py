#!/usr/bin/env python
"""
The main CLI executable.

Copyright (c) 2010-2011 iXsystems, Inc., All rights reserved.

See COPYING for more details.

Garrett Cooper, October 2011
"""

import getpass
import os
import socket
import sys

import core.cli

class Main(core.cli.CLI):
    """A subclass for the top-level CLI."""

    # Characters to replace in _prompt_fmt
    #_repl_chars = ()

    def __init__(self, interactive=True):

        self.subcommands = (
            'services.cli.Services',
            'storage.cli.Storage',
        )

        methods = filter(lambda x: x.startswith('_repl_') and \
                                   callable(getattr(self, x, None)), dir(self))
        self._repl_chars = map(lambda x: x.replace('_repl_', ''), methods)

        self._prompt_fmt = '\\u@\\h> '

        core.cli.CLI.__init__(self, interactive=interactive)

    # The following values could easily be cached somewhere..

    def _repl_h(self):
        return socket.gethostname().split('.')[0]

    def _repl_u(self):
        return getpass.getuser()

    def _repl_w(self):
        return os.getcwd()

    def preloop(self):
        if self._interactive:
            # This should be cached too..
            prompt = self._prompt_fmt
            for char in self._repl_chars:
                method = getattr(self, '_repl_' + char)
                prompt = prompt.replace('\\' + char, method())
            self.prompt = prompt

    # Commands follow..

    def do_exit(self, arg):
        """Exit from the CLI."""
        sys.exit(0)

    do_quit = do_exit

if __name__ == '__main__':
    core.cli.main(Main)

# vim: syntax=python
