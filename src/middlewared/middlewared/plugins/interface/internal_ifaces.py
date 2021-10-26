from middlewared.service import private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    async def internal_interfaces(self):
        return ['wg', 'lo', 'tun', 'tap', 'docker', 'veth', 'kube-bridge', 'kube-dummy-if', 'vnet', 'openvpn']
