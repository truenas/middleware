from middlewared.service import private, Service


class FencedForceService(Service):

    class Config:
        namespace = 'failover.fenced'

    @private
    def force(self):

        # TODO
        # Return False always until fenced daemon
        # can be written to work on Linux.
        return False
