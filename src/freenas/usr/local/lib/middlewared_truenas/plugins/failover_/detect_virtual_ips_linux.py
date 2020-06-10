from middlewared.service import private, Service


class DetectVirtualIpStates(Service):

    class Config:
        namespace = 'failover.vip'

    @private
    async def get_states(self, interfaces=None):

        # TODO
        # For now, we return empty until the freeBSD carp
        # specific items can be moved to the platform
        # dependent sections in middlewared and until VRRP
        # can be implemented.
        return [], [], []

    @private
    async def check_states(self, local, remote):

        # TODO
        # Read above comment.
        return []
