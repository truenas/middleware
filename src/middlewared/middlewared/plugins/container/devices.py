from truenas_pylibvirt.utils.pci import (
    get_pci_device_default_data, get_all_pci_devices_details, get_single_pci_device_details,
)
from truenas_pylibvirt.utils.usb import find_usb_device_by_libvirt_name, get_all_usb_devices

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    ContainerDeviceEntry,
    ContainerDeviceNicAttachChoicesArgs, ContainerDeviceNicAttachChoicesResult,
    ContainerDeviceCreateArgs, ContainerDeviceCreateResult,
    ContainerDeviceUpdateArgs, ContainerDeviceUpdateResult,
    ContainerDeviceDeleteArgs, ContainerDeviceDeleteResult,
    ContainerDeviceUsbDeviceArgs, ContainerDeviceUsbDeviceResult,
    ContainerDeviceUsbChoicesArgs, ContainerDeviceUsbChoicesResult,
    ContainerDevicePciDeviceArgs, ContainerDevicePciDeviceResult,
    ContainerDevicePciDeviceChoicesArgs, ContainerDevicePciDeviceChoicesResult,
)
from middlewared.service import CRUDService, private
from middlewared.utils.libvirt.device_factory import DeviceFactory
from middlewared.utils.libvirt.mixin import DeviceMixin


class ContainerDeviceModel(sa.Model):
    __tablename__ = 'container_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    attributes = sa.Column(sa.JSON(encrypted=True))
    container_id = sa.Column(sa.ForeignKey('container_container.id'), index=True)


class ContainerDeviceService(CRUDService, DeviceMixin):

    class Config:
        namespace = 'container.device'
        datastore = 'container.device'
        datastore_extend = 'container.device.extend_device'
        cli_namespace = 'service.container.device'
        role_prefix = 'CONTAINER_DEVICE'
        entry = ContainerDeviceEntry

    @property
    def _service_type(self):
        return 'container'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.device_factory = DeviceFactory(self.middleware)

    @private
    async def extend_device(self, device):
        if device['container']:
            device['container'] = device['container']['id']
        return device

    @api_method(ContainerDeviceCreateArgs, ContainerDeviceCreateResult)
    async def do_create(self, data):
        """
        Create a new device for the container of id `container`.
        """
        return await self._create_impl(data)

    @api_method(ContainerDeviceUpdateArgs, ContainerDeviceUpdateResult)
    async def do_update(self, id_, data):
        """
        Update a container device of `id`.
        """
        return await self._update_impl(id_, data)

    @api_method(ContainerDeviceDeleteArgs, ContainerDeviceDeleteResult)
    async def do_delete(self, id_, options):
        """
        Delete a container device of `id`.
        """
        return await self._delete_impl(id_, options)

    @api_method(
        ContainerDeviceNicAttachChoicesArgs, ContainerDeviceNicAttachChoicesResult, roles=['CONTAINER_DEVICE_READ']
    )
    async def nic_attach_choices(self):
        """
        Available choices for NIC Attach attribute.
        """
        container_bridge = await self.middleware.call('container.bridge_name')
        return (await self.middleware.call('interface.choices', {'exclude': ['epair', 'tap', 'vnet']})) | {
            container_bridge: container_bridge
        }

    @api_method(
        ContainerDeviceUsbDeviceArgs, ContainerDeviceUsbDeviceResult,
        roles=['CONTAINER_DEVICE_READ']
    )
    def usb_device(self, device):
        """
        Retrieve details about `device` USB device.
        """
        return find_usb_device_by_libvirt_name(device)

    @api_method(
        ContainerDeviceUsbChoicesArgs, ContainerDeviceUsbChoicesResult,
        roles=['CONTAINER_DEVICE_READ']
    )
    def usb_choices(self):
        """
        Available choices for USB passthrough devices.
        """
        return get_all_usb_devices()

    @api_method(
        ContainerDevicePciDeviceArgs, ContainerDevicePciDeviceResult, roles=['CONTAINER_DEVICE_READ']
    )
    def pci_device(self, device):
        """Retrieve details about `device` PCI device"""
        if device_details := get_single_pci_device_details(device):
            return device_details[device]
        else:
            return {
                **get_pci_device_default_data(),
                'error': 'Device not found',
            }

    @api_method(
        ContainerDevicePciDeviceChoicesArgs, ContainerDevicePciDeviceChoicesResult,
        roles=['CONTAINER_DEVICE_READ']
    )
    def pci_device_choices(self):
        """Available choices for PCI passthru devices"""
        return get_all_pci_devices_details()
