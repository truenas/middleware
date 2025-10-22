import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    ContainerDeviceEntry, ContainerDeviceDiskChoicesArgs, ContainerDeviceDiskChoicesResult,
    ContainerDeviceIotypeChoicesArgs, ContainerDeviceIotypeChoicesResult,
    ContainerDeviceNicAttachChoicesArgs, ContainerDeviceNicAttachChoicesResult,
    ContainerDeviceCreateArgs, ContainerDeviceCreateResult,
    ContainerDeviceUpdateArgs, ContainerDeviceUpdateResult,
    ContainerDeviceDeleteArgs, ContainerDeviceDeleteResult,
)
from middlewared.service import CRUDService, private
from middlewared.utils.libvirt.device_factory import DeviceFactory
from middlewared.utils.libvirt.mixin import DeviceMixin


class ContainerDeviceModel(sa.Model):
    __tablename__ = 'container_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    attributes = sa.Column(sa.JSON(encrypted=True))
    container_id = sa.Column(sa.ForeignKey('container_container.id'), index=True)
    order = sa.Column(sa.Integer(), nullable=True)


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

        if not device['order']:
            if device['attributes']['dtype'] == 'CDROM':
                device['order'] = 1000
            elif device['attributes']['dtype'] in ('DISK', 'RAW'):
                device['order'] = 1001
            else:
                device['order'] = 1002
        # FIXME: We need to fix order for VMs/containers
        return device

    @api_method(ContainerDeviceCreateArgs, ContainerDeviceCreateResult)
    async def do_create(self, data):
        """
        Create a new device for the container of id `container`.

        If `attributes.dtype` is the `RAW` type and a new raw file is to be created, `attributes.exists` will be
        passed as false. This means the API handles creating the raw file and raises the appropriate exception if
        file creation fails.

        If `attributes.dtype` is of `DISK` type and a new Zvol is to be created, `attributes.create_zvol` will be
        passed as true with valid `attributes.zvol_name` and `attributes.zvol_volsize` values.
        """
        return await self._create_impl(data)

    @api_method(ContainerDeviceUpdateArgs, ContainerDeviceUpdateResult)
    async def do_update(self, id_, data):
        """
        Update a container device of `id`.

        Pass `attributes.size` to resize a `dtype` `RAW` device. The raw file will be resized.
        """
        return await self._update_impl(id_, data)

    @api_method(ContainerDeviceDeleteArgs, ContainerDeviceDeleteResult)
    async def do_delete(self, id_, options):
        """
        Delete a container device of `id`.
        """
        return await self._delete_impl(id_, options)

    @api_method(ContainerDeviceDiskChoicesArgs, ContainerDeviceDiskChoicesResult, roles=['CONTAINER_DEVICE_READ'])
    async def disk_choices(self):
        """
        Returns disk choices for device type "DISK".
        """
        return await self._disk_choices()

    @api_method(ContainerDeviceIotypeChoicesArgs, ContainerDeviceIotypeChoicesResult, roles=['CONTAINER_DEVICE_READ'])
    async def iotype_choices(self):
        """
        IO-type choices for storage devices.
        """
        return self._iotype_choices()

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
