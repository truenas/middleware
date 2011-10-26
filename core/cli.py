"""
Core CLI logic.

Copyright (c) 2010-2011 iXsystems, Inc., All rights reserved.

See COPYING for more details.

Garrett Cooper, October 2011
"""

import cmd
import readline
import sys

def _print(msg):
    """Print out the contents of 'msg' to standard out and log via the logger
       mechanism.

       Append a newline to match the print built-in.
    """
    sys.stdout.write(msg + '\n')

class CLI(cmd.Cmd):
    """A superclass for all CLI commands.

       Serviceable parts you as a developer care about are:

       - register_subcommand: for registering subcommands as part of the
                              current command.

    """

    def __init__(self, interactive=True):
        cmd.Cmd.__init__(self)
        classname = str(self.__class__).split('.')[-1]
        self.prompt = '%s> ' % (classname.lower(), )
        self._interactive = interactive

        subcommands = getattr(self, 'subcommands', [])
        for subcommand in subcommands:
            self.register_subcommand(subcommand)

    def do_EOF(self, arg):
        """Dummy EOF handler"""
        raise EOFError

    def register_subcommand(self, subcommand):
        """Register a subcommand as part of a CLI
        """

        sc_mod = '.'.join(subcommand.split('.')[:-1])
        sc_class = subcommand.split('.')[-1]

        def do_sc(m, c):
            o = None
            # Create the CLI subcommand object.
            exec('import %s; o = %s.%s()' % (m, m, c, )) in locals(), globals()
            # Create the CLI hook.
            o.cmdloop()
            return lambda o: o.cmdloop()
        setattr(self, 'do_%s' % (sc_class.lower(), ), do_sc(sc_mod, sc_class))

def main(cli_cls):
    """Loads the respective CLI class as the top-level command

    XXX: this should be loaded via details returned with the inspect module."""

    # Don't create a history file.
    readline.set_history_length(0)
    interactive = sys.stdout.isatty() and len(sys.argv) == 1
    m = cli_cls(interactive=interactive)
    try:
        while True:
            try:
                m.cmdloop()
            except (EOFError):
                _print('')
            except (KeyboardInterrupt):
                _print('')
                break
    finally:
        pass
