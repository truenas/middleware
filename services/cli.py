"""
The service CLI.

Copyright (c) 2010-2011 iXsystems, Inc., All rights reserved.

See COPYING for more details.

Garrett Cooper, October 2011
"""

import core.cli

class Services(core.cli.CLI):
    """A superclass for managing services."""

    def __init__(self):
        core.cli.CLI.__init__(self)

    def do_start(self, arg):
        """Start a service"""
        raise NotImplementedError

    def do_stop(self, arg):
        """Stop a service"""
        raise NotImplementedError

    def do_restart(self, arg):
        """Restart a service"""
        raise NotImplementedError

    def do_reload(self, arg):
        """Reload a service's configuration"""
        raise NotImplementedError
