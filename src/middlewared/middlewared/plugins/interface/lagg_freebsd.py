from middlewared.service import Service

from .lagg_base import InterfaceLaggBase


class InterfaceService(Service, InterfaceLaggBase):

    class Config:
        namespace_alias = 'interfaces'

    async def lagg_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE', 'ROUNDROBIN', 'NONE']
