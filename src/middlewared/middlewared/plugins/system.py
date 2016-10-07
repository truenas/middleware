from middlewared.schema import accepts
from middlewared.service import Service


class SystemService(Service):

    @accepts()
    def is_freenas(self):
        """
        Returns `true` if running system is a FreeNAS or `false` is Something Else.
        """
        # This is a stub calling notifier until we have all infrastructure
        # to implement in middlewared
        return self.middleware.call('notifier.is_freenas')
