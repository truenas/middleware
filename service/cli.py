"""
The service base CLI.

Copyright (c) 2010-2011 iXsystems, Inc., All rights reserved.

See COPYING for more details.

Garrett Cooper, October 2011
"""

from core.cli import CLI

from middleware.callbacks import service_callbacks

class ServiceCLI(CLI):
    """A superclass for managing services."""

    def do_configure(self, arg):
        """Configure a service"""

        svc = arg[0]

        if svc in service_callbacks.get_registered_services():
            # TODO: create a mechanism for configuring a service on the fly
            # here.

    def do_start(self, arg):
        """Start a service"""

        svc = arg[0]

        service_callbacks.start(svc)

    def do_stop(self, arg):
        """Stop a service"""

        svc = arg[0]

        service_callbacks.stop(svc)

    def do_restart(self, arg):
        """Restart a service"""

        svc = arg[0]

        service_callbacks.restart(svc)

    def do_reload(self, arg):
        """Reload a service configuration"""

        svc = arg[0]

        try:
            service_callbacks.reload(svc)
        except NotImplementedError:
            service_callbacks.restart(svc)
