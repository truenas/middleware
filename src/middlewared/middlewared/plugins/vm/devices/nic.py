import random

from middlewared.api.current import VMNICDevice
from middlewared.plugins.interface.netif import netif
from middlewared.schema import Dict
from middlewared.service import CallError

from .device import Device
from .utils import create_element


class NIC(Device):

    schema = Dict(
        'attributes',
    )
    schema_model = VMNICDevice

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bridge = self.bridge_created = self.nic_attach = None

    def identity(self):
        nic_attach = self.data['attributes'].get('nic_attach')
        if not nic_attach:
            nic_attach = netif.RoutingTable().default_route_ipv4.interface
        return nic_attach

    def is_available(self):
        return self.identity() in netif.list_interfaces()

    @staticmethod
    def random_mac():
        mac_address = [
            0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)
        ]
        return ':'.join(['%02x' % x for x in mac_address])

    def setup_nic_attach(self):
        nic_attach = self.data['attributes'].get('nic_attach')
        interfaces = netif.list_interfaces()
        if nic_attach and nic_attach not in interfaces:
            raise CallError(f'{nic_attach} not found.')
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

        self.nic_attach = nic.name

    def xml_children(self):
        return [
            create_element('model', type='virtio' if self.data['attributes']['type'] == 'VIRTIO' else 'e1000'),
            create_element(
                'mac', address=self.data['attributes']['mac'] if
                self.data['attributes'].get('mac') else self.random_mac()
            ),
        ]

    def xml(self, *args, **kwargs):
        self.setup_nic_attach()
        if self.nic_attach.startswith('br'):
            return create_element(
                'interface', type='bridge', attribute_dict={
                    'children': [
                        create_element('source', bridge=self.nic_attach)
                    ] + self.xml_children()
                }
            )
        else:
            trust_guest_rx_filters = 'yes' if self.data['attributes']['trust_guest_rx_filters'] else 'no'
            return create_element(
                'interface', type='direct', trustGuestRxFilters=trust_guest_rx_filters, attribute_dict={
                    'children': [
                        create_element('source', dev=self.nic_attach, mode='bridge')
                    ] + self.xml_children()
                }
            )

    def _validate(self, device, verrors, old=None, vm_instance=None, update=True):
        nic = device['attributes'].get('nic_attach')
        if nic:
            nic_choices = self.middleware.call_sync('vm.device.nic_attach_choices')
            if nic not in nic_choices:
                verrors.add('attributes.nic_attach', 'Not a valid choice.')
            elif nic.startswith('br') and device['attributes']['trust_guest_rx_filters']:
                verrors.add(
                    'attributes.trust_guest_rx_filters',
                    'This can only be set when "nic_attach" is not a bridge device'
                )
        if device['attributes']['trust_guest_rx_filters'] and device['attributes']['type'] == 'E1000':
            verrors.add(
                'attributes.trust_guest_rx_filters',
                'This can only be set when "type" of NIC device is "VIRTIO"'
            )

        mac_address = device['attributes'].get('mac')
        if mac_address and mac_address.lower().startswith('ff'):
            verrors.add('attributes.mac', 'MAC address must not start with `ff`')
