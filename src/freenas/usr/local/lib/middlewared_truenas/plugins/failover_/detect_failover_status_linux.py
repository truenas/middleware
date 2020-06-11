from middlewared.service import private, Service


class DetectFailoverStatusService(Service):

    class Config:
        namespace = 'failover.status'

    @private
    async def get_local(self, app):

        # TODO
        # return SINGLE always on Linux until VRRP can be
        # implemented.

        return 'SINGLE'
