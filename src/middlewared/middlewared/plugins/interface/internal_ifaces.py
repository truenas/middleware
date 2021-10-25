from middlewared.service import Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    async def internal_interfaces(self):
        return ['wg', 'lo', 'tun', 'tap', 'docker', 'veth', 'kube-bridge', 'kube-dummy-if', 'vnet', 'openvpn']
