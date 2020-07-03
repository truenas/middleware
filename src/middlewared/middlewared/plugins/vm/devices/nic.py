import random
import netif

from middlewared.schema import Dict, Str
from middlewared.service import CallError

from .device import Device
from .utils import create_element


class NIC(Device):

    schema = Dict(
        'attributes',
        Str('type', enum=['E1000', 'VIRTIO'], default='E1000'),
        Str('nic_attach', default=None, null=True),
        Str('mac', default=None, null=True),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bridge = self.bridge_created = None

    @staticmethod
    def random_mac():
        mac_address = [
            0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)
        ]
        return ':'.join(['%02x' % x for x in mac_address])

    def pre_start_vm_freebsd(self, *args, **kwargs):
        nic_attach = self.data['attributes']['nic_attach']
        interfaces = netif.list_interfaces()
        bridge = None
        if nic_attach and nic_attach not in interfaces:
            raise CallError(f'{nic_attach} not found.')
        elif nic_attach and nic_attach.startswith('bridge'):
            bridge = interfaces[nic_attach]
        else:
            if not nic_attach:
                try:
                    nic_attach = netif.RoutingTable().default_route_ipv4.interface
                    nic = netif.get_interface(nic_attach)
                except Exception as e:
                    raise CallError(f'Unable to retrieve default interface: {e}')
            else:
                nic = netif.get_interface(nic_attach)

            if netif.InterfaceFlags.UP not in nic.flags:
                nic.up()

        if not bridge:
            for iface in filter(lambda v: v.startswith('bridge'), interfaces):
                if nic_attach in interfaces[iface].members:
                    bridge = interfaces[iface]
                    break
            else:
                bridge = netif.get_interface(netif.create_interface('bridge'))
                bridge.add_member(nic_attach)
                self.bridge_created = True

        if netif.InterfaceFlags.UP not in bridge.flags:
            bridge.up()

        self.bridge = bridge.name

    def pre_start_vm_rollback_freebsd(self, *args, **kwargs):
        if self.bridge_created and self.bridge in netif.list_interfaces():
            netif.destroy_interface(self.bridge)
            self.bridge = self.bridge_created = None

    def xml_freebsd(self, *args, **kwargs):
        return create_element(
            'interface', type='bridge', attribute_dict={
                'children': [
                    create_element('source', bridge=self.bridge or ''),
                    create_element('model', type='virtio' if self.data['attributes']['type'] == 'VIRTIO' else 'e1000'),
                    create_element(
                        'mac', address=self.data['attributes']['mac'] if
                        self.data['attributes'].get('mac') else self.random_mac()
                    ),
                    create_element('address', type='pci', slot=str(kwargs['slot'])),
                ]
            }
        )
