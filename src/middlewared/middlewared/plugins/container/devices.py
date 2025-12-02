from truenas_pylibvirt.utils.usb import get_all_usb_devices

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    ContainerDeviceEntry,
    ContainerDeviceNicAttachChoicesArgs, ContainerDeviceNicAttachChoicesResult,
    ContainerDeviceCreateArgs, ContainerDeviceCreateResult,
    ContainerDeviceUpdateArgs, ContainerDeviceUpdateResult,
    ContainerDeviceDeleteArgs, ContainerDeviceDeleteResult,
    ContainerDeviceUsbChoicesArgs, ContainerDeviceUsbChoicesResult,
    ContainerDeviceGpuChoicesArgs, ContainerDeviceGpuChoicesResult,
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

    @api_method(
        ContainerDeviceCreateArgs,
        ContainerDeviceCreateResult,
        audit='Container device create',
        audit_extended=lambda data: f'{data["attributes"]["dtype"]}',
    )
    async def do_create(self, data):
        """
        Create a new device for the container of id `container`.
        """
        return await self._create_impl(data)

    @api_method(
        ContainerDeviceUpdateArgs,
        ContainerDeviceUpdateResult,
        audit='Container device update',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update a container device of `id`.
        """
        return await self._update_impl(id_, data, audit_callback)

    @api_method(
        ContainerDeviceDeleteArgs,
        ContainerDeviceDeleteResult,
        audit='Container device delete',
        audit_callback=True,
    )
    async def do_delete(self, audit_callback, id_, options):
        """
        Delete a container device of `id`.
        """
        return await self._delete_impl(id_, options, audit_callback)

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
        ContainerDeviceUsbChoicesArgs, ContainerDeviceUsbChoicesResult,
        roles=['CONTAINER_DEVICE_READ']
    )
    def usb_choices(self):
        """
        Available choices for USB passthrough devices.
        """
        return get_all_usb_devices()

    @api_method(
        ContainerDeviceGpuChoicesArgs, ContainerDeviceGpuChoicesResult,
        roles=['CONTAINER_DEVICE_READ']
    )
    async def gpu_choices(self):
        """
        Available choices for GPU devices.
        """
        return {
            gpu['addr']['pci_slot']: gpu['vendor']
            for gpu in await self.middleware.call('device.get_gpus')
            if gpu['vendor'] in ('AMD', 'INTEL', 'NVIDIA') and gpu['available_to_host']
        }
