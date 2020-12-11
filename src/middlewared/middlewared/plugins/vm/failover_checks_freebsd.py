import netif

from middlewared.service import Service

from .failover_check_base import FailoverChecksBase


class VMDeviceService(Service, FailoverChecksBase):

    class Config:
        namespace = 'vm.device'

    async def nic_capability_checks(self, vm_devices=None, check_system_iface=True):
        vm_nics = []
        system_ifaces = {i['name']: i for i in await self.middleware.call('interface.query')}
        for vm_device in await self.middleware.call(
            'vm.device.query', [
                ['dtype', '=', 'NIC'], [
                    'OR', [['attributes.nic_attach', '=', None], ['attributes.nic_attach', '!^', 'bridge']]
                ]
            ]
        ) if not vm_devices else vm_devices:
            try:
                nic = vm_device['attributes'].get('nic_attach') or netif.RoutingTable().default_route_ipv4.interface
            except Exception:
                nic = None
            if nic in system_ifaces and (
                not check_system_iface or not system_ifaces[nic]['disable_offload_capabilities']
            ):
                vm_nics.append(nic)
        return vm_nics
