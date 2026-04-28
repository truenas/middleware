from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.current import (
    QueryOptions,
    VMDeviceCreate,
    VMDeviceDeleteOptions,
    VMDeviceEntry,
    VMDeviceUpdate,
    VMDiskDevice,
    VMRAWDevice,
    ZFSResourceQuery,
)
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.service import CallError, CRUDServicePart, ServiceContext, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.libvirt.utils import ACTIVE_STATES

if TYPE_CHECKING:
    from middlewared.utils.libvirt.device_factory import DeviceFactory
    from middlewared.utils.types import AuditCallback


class VMDeviceModel(sa.Model):
    __tablename__ = 'vm_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    attributes = sa.Column(sa.JSON(dict, encrypted=True))
    vm_id = sa.Column(sa.ForeignKey('vm_vm.id'), index=True)
    order = sa.Column(sa.Integer(), nullable=True)


class VMDeviceServicePart(CRUDServicePart[VMDeviceEntry]):
    _datastore = 'vm.device'
    _entry = VMDeviceEntry

    def __init__(self, context: ServiceContext, device_factory: DeviceFactory) -> None:
        super().__init__(context)
        self.device_factory = device_factory

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if data['vm']:
            data['vm'] = data['vm']['id']
        if not data['order']:
            if data['attributes']['dtype'] == 'CDROM':
                data['order'] = 1000
            elif data['attributes']['dtype'] in ('DISK', 'RAW'):
                data['order'] = 1001
            else:
                data['order'] = 1002
        return data

    async def do_create(self, data: VMDeviceCreate) -> VMDeviceEntry:
        data_dict = data.model_dump(by_alias=True, context={'expose_secrets': True})
        await self._validate_device(data_dict, update=False)
        data_dict = await self._update_device(data_dict)
        id_ = await self.middleware.call('datastore.insert', self._datastore, data_dict)
        await self._reorder_devices(id_, data_dict['vm'], data_dict.get('order'))
        return await self.get_instance(id_)

    async def do_update(
        self, id_: int, data: VMDeviceUpdate, *, audit_callback: AuditCallback,
    ) -> VMDeviceEntry:
        device = await self.get_instance(id_)
        device_dict = device.model_dump(by_alias=True, context={'expose_secrets': True})
        data_dict = data.model_dump(exclude_unset=True, by_alias=True)
        new_attrs = data_dict.pop('attributes', {})
        device_dict.update(data_dict)
        device_dict['attributes'].update(new_attrs)
        audit_callback(device_dict['attributes']['dtype'])

        # We have to do this specially because of how we want to allow to optionally
        # update attributes dict
        # In the pydantic model, we have -> attributes: dict
        # This means that someone can send something wrong here and when we try
        # to make libvirt device out of it, it will error out before we actually validate
        # device itself
        validate_model(self._entry, device_dict)
        old_dict = device.model_dump(by_alias=True, context={'expose_secrets': True})
        await self._validate_device(device_dict, old_dict)
        device_dict = await self._update_device(device_dict, old_dict)
        await self.middleware.call('datastore.update', self._datastore, id_, device_dict)
        await self._reorder_devices(id_, device.vm, device_dict.get('order'))
        return await self.get_instance(id_)

    async def do_delete(
        self, id_: int, options: VMDeviceDeleteOptions, *, audit_callback: AuditCallback,
    ) -> bool:
        device = await self.get_instance(id_)
        audit_callback(device.attributes.dtype)
        vm = await self.call2(self.s.vm.get_instance, device.vm)
        if vm.status.state in ACTIVE_STATES:
            raise CallError('Please stop/resume associated VM before deleting VM device.')

        try:
            await self._delete_resource(options, device)
        except CallError:
            if not options.force:
                raise

        return bool(await self.middleware.call('datastore.delete', self._datastore, id_))

    async def _delete_resource(self, options: VMDeviceDeleteOptions, device: VMDeviceEntry) -> None:
        if options.zvol:
            if not isinstance(device.attributes, VMDiskDevice):
                raise CallError('The device is not a disk and has no zvol to destroy.')
            path = device.attributes.path or ''
            if not path.startswith('/dev/zvol'):
                raise CallError('Unable to destroy zvol as disk device has misconfigured path')
            zvol_id = zvol_path_to_name(path)
            if await self.call2(
                self.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[zvol_id], properties=None)
            ):
                # FIXME: What about FS attachment? Also should we be stopping the vm only when
                # deleting an attachment ?
                await self.call2(self.s.zfs.resource.destroy_impl, zvol_id)
        if options.raw_file:
            if not isinstance(device.attributes, VMRAWDevice):
                raise CallError('Device is not of RAW type.')
            if not device.attributes.path:
                raise CallError('RAW device has no path configured')
            try:
                os.unlink(device.attributes.path)
            except OSError:
                raise CallError(f'Failed to destroy {device.attributes.path!r}')

    async def _validate_device(
        self, device: dict[str, Any], old: dict[str, Any] | None = None, update: bool = True,
    ) -> None:
        svc_instance = (await self.call2(self.s.vm.get_instance, device['vm'])).model_dump(by_alias=True)
        verrors = ValidationErrors()
        if old and old['attributes']['dtype'] != device['attributes']['dtype']:
            verrors.add('attributes.dtype', 'Device type cannot be changed')
        verrors.check()
        device_adapter = self.device_factory.get_device_adapter(device)
        await self.middleware.run_in_thread(device_adapter.validate, old, svc_instance, update)

    async def _update_device(
        self, data: dict[str, Any], old: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        device_dtype = data['attributes']['dtype']
        if device_dtype == 'DISK':
            create_zvol = data['attributes'].pop('create_zvol', False)
            if create_zvol:
                ds_options: dict[str, Any] = {
                    'name': data['attributes'].pop('zvol_name'),
                    'type': 'VOLUME',
                    'volsize': data['attributes'].pop('zvol_volsize'),
                }
                zvol_blocksize = await self.middleware.call(
                    'pool.dataset.recommended_zvol_blocksize', ds_options['name'].split('/', 1)[0]
                )
                ds_options['volblocksize'] = zvol_blocksize
                await self.middleware.call('pool.dataset.create', ds_options)
        elif device_dtype == 'RAW' and (
            not data['attributes'].pop('exists', True) or (
                old and old['attributes']['size'] != data['attributes']['size']
            )
        ):
            path = data['attributes']['path']
            cp = await run(['truncate', '-s', str(data['attributes']['size']), path], check=False)
            if cp.returncode:
                raise CallError(f'Failed to create or update raw file {path}: {cp.stderr.decode()}')
        return data

    async def _reorder_devices(self, id_: int, vm_id: int, order: int | None) -> None:
        if order is None:
            return

        filters: list[list[Any]] = [['vm', '=', vm_id], ['id', '!=', id_]]
        conflicts = await self.call2(
            self.s.vm.device.query, filters + [['order', '=', order]],
        )
        if not conflicts:
            return

        used_order = [order]
        all_devices = await self.call2(
            self.s.vm.device.query, filters, QueryOptions(order_by=['order']),
        )
        for device in all_devices:
            if not device.order:
                continue

            if device.order not in used_order:
                used_order.append(device.order)
                continue

            new_order = min(used_order) + 1
            while new_order in used_order:
                new_order += 1
            used_order.append(new_order)
            await self.middleware.call(
                'datastore.update', self._datastore, device.id, {'order': new_order}
            )


async def validate_display_devices(verrors: ValidationErrors, vm_instance: dict[str, Any]) -> None:
    devs = get_display_devices(vm_instance)
    if len(devs['spice']) > 1:
        verrors.add('attributes.type', 'Only one SPICE Display device is supported')
    if len(devs['vnc']) > 1:
        verrors.add('attributes.type', 'Only one VNC Display device is supported')


def get_display_devices(vm_instance: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    devs: dict[str, list[dict[str, Any]]] = {'spice': [], 'vnc': []}
    for dev in filter(lambda d: d['attributes']['dtype'] == 'DISPLAY', vm_instance['devices']):
        if dev['attributes']['type'] == 'SPICE':
            devs['spice'].append(dev)
        else:
            devs['vnc'].append(dev)
    return devs
