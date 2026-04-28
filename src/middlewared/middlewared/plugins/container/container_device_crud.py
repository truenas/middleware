from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.current import (
    ContainerDeviceCreate,
    ContainerDeviceDeleteOptions,
    ContainerDeviceEntry,
    ContainerDeviceUpdate,
)
from middlewared.service import CallError, CRUDServicePart, ServiceContext, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.libvirt.utils import ACTIVE_STATES

if TYPE_CHECKING:
    from middlewared.utils.libvirt.device_factory import DeviceFactory
    from middlewared.utils.types import AuditCallback


class ContainerDeviceModel(sa.Model):
    __tablename__ = 'container_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    attributes = sa.Column(sa.JSON(dict, encrypted=True))
    container_id = sa.Column(sa.ForeignKey('container_container.id'), index=True)


class ContainerDeviceServicePart(CRUDServicePart[ContainerDeviceEntry]):
    _datastore = 'container.device'
    _entry = ContainerDeviceEntry

    def __init__(self, context: ServiceContext, device_factory: DeviceFactory) -> None:
        super().__init__(context)
        self.device_factory = device_factory

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if data['container']:
            data['container'] = data['container']['id']
        return data

    async def do_create(self, data: ContainerDeviceCreate) -> ContainerDeviceEntry:
        data_dict = data.model_dump(by_alias=True)
        await self._validate_device(data_dict)
        id_ = await self.middleware.call('datastore.insert', self._datastore, data_dict)
        return await self.get_instance(id_)

    async def do_update(
        self, id_: int, data: ContainerDeviceUpdate, *, audit_callback: AuditCallback,
    ) -> ContainerDeviceEntry:
        device = await self.get_instance(id_)
        device_dict = device.model_dump(by_alias=True)
        data_dict = data.model_dump(exclude_unset=True, by_alias=True)
        new_attrs = data_dict.pop('attributes', {})
        device_dict.update(data_dict)
        device_dict['attributes'].update(new_attrs)
        audit_callback(device_dict['attributes']['dtype'])

        validate_model(self._entry, device_dict)
        await self._validate_device(device_dict, device.model_dump(by_alias=True))
        await self.middleware.call('datastore.update', self._datastore, id_, device_dict)
        return await self.get_instance(id_)

    async def do_delete(
        self, id_: int, options: ContainerDeviceDeleteOptions, *, audit_callback: AuditCallback,
    ) -> bool:
        device = await self.get_instance(id_)
        audit_callback(device.attributes.dtype)
        container = await self.call2(self.s.container.get_instance, device.container)
        if container.status.state in ACTIVE_STATES:
            raise CallError(
                'Please stop/resume associated CONTAINER before deleting CONTAINER device.'
            )
        if options.zvol:
            raise CallError('The device is not a disk and has no zvol to destroy.')
        if options.raw_file:
            raise CallError('Device is not of RAW type.')
        return bool(await self.middleware.call('datastore.delete', self._datastore, id_))

    async def _validate_device(
        self, device: dict[str, Any], old: dict[str, Any] | None = None,
    ) -> None:
        svc_instance = (await self.call2(
            self.s.container.get_instance, device['container']
        )).model_dump(by_alias=True)
        verrors = ValidationErrors()
        if old and old['attributes']['dtype'] != device['attributes']['dtype']:
            verrors.add('attributes.dtype', 'Device type cannot be changed')
        verrors.check()
        device_adapter = self.device_factory.get_device_adapter(device)
        await self.middleware.run_in_thread(device_adapter.validate, old, svc_instance, True)
