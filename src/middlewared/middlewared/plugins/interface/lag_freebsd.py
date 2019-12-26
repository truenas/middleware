from middlewared.service import Service

from .lag_base import InterfaceLagBase


class InterfaceService(Service, InterfaceLagBase):

    class Config:
        namespace_alias = 'interfaces'

    async def lag_supported_protocols(self):
        return ['LACP', 'FAILOVER', 'LOADBALANCE', 'ROUNDROBIN', 'NONE']
