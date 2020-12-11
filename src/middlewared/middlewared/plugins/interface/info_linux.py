from middlewared.service import Service

from .info_base import InterfaceInfoBase


class InterfaceService(Service, InterfaceInfoBase):

    class Config:
        namespace_alias = 'interfaces'

    async def internal_interfaces(self):
        return ['lo', 'tun', 'tap', 'bond', 'docker', 'veth', 'kube-bridge', 'kube-dummy-if', 'vnet', 'openvpn']
