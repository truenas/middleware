import copy
import os

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.plugins.zfs.destroy_impl import DestroyArgs
from middlewared.service import CallError, private
from middlewared.utils import run

from .storage_devices import IOTYPE_CHOICES
from .utils import ACTIVE_STATES


class DeviceMixin:

    @property
    def _service_type(self) -> str:
        ...

    async def _create_impl(self, data):
        data = await self._validate_device(data, update=False)
        data = await self._update_device(data)

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data
        )
        await self.__reorder_devices(id_, data[self._service_type], data.get('order'))

        return await self.get_instance(id_)

    async def _update_impl(self, id_, data):
        device = await self.get_instance(id_)
        new = copy.deepcopy(device)
        new_attrs = data.pop('attributes', {})
        new.update(data)
        new['attributes'].update(new_attrs)

        new = await self._validate_device(new, device)
        new = await self._update_device(new, device)

        await self.middleware.call('datastore.update', self._config.datastore, id_, new)
        await self.__reorder_devices(id_, device[self._service_type], new.get('order'))

        return await self.get_instance(id_)

    async def _delete_impl(self, id_, options):
        device = await self.get_instance(id_)
        status = (
            await self.middleware.call(f'{self._service_type}.get_instance', device[self._service_type])
        )['status']
        if status['state'] in ACTIVE_STATES:
            raise CallError(
                f'Please stop/resume associated {self._service_type.upper()} before '
                f'deleting {self._service_type.upper()} device.'
            )

        try:
            await self._delete_resource(options, device)
        except CallError:
            if not options['force']:
                raise

        return await self.middleware.call('datastore.delete', self._config.datastore, id_)

    async def __reorder_devices(self, id_, instance_id, order):
        if order is None:
            return
        filters = [(self._service_type, '=', instance_id), ('id', '!=', id_)]
        if await self.middleware.call(f'{self._service_type}.device.query', filters + [('order', '=', order)]):
            used_order = [order]
            for device in await self.middleware.call(
                f'{self._service_type}.device.query', filters, {'order_by': ['order']}
            ):
                if not device['order']:
                    continue

                if device['order'] not in used_order:
                    used_order.append(device['order'])
                    continue

                device['order'] = min(used_order) + 1
                while device['order'] in used_order:
                    device['order'] += 1
                used_order.append(device['order'])
                await self.middleware.call('datastore.update', self._config.datastore, device['id'], device)

    async def _delete_resource(self, options, device):
        device_dtype = device['attributes']['dtype']
        if options['zvol']:
            if device_dtype != 'DISK':
                raise CallError('The device is not a disk and has no zvol to destroy.')
            if not device['attributes'].get('path', '').startswith('/dev/zvol'):
                raise CallError('Unable to destroy zvol as disk device has misconfigured path')
            zvol_id = zvol_path_to_name(device['attributes']['path'])
            if await self.middleware.call(
                'zfs.resource.query_impl', {'paths': [zvol_id], 'properties': None}
            ):
                # FIXME: What about FS attachment? Also should we be stopping the vm only when
                # deleting an attachment ?
                await self.middleware.call('zfs.resource.destroy_impl', DestroyArgs(path=zvol_id))
        if options['raw_file']:
            if device_dtype != 'RAW':
                raise CallError('Device is not of RAW type.')
            try:
                os.unlink(device['attributes']['path'])
            except OSError:
                raise CallError(f'Failed to destroy {device["attributes"]["path"]}')

    async def _update_device(self, data, old=None):
        device_dtype = data['attributes']['dtype']
        if device_dtype == 'DISK':
            create_zvol = data['attributes'].pop('create_zvol', False)

            if create_zvol:
                ds_options = {
                    'name': data['attributes'].pop('zvol_name'),
                    'type': 'VOLUME',
                    'volsize': data['attributes'].pop('zvol_volsize'),
                }

                self.logger.debug(f'Creating ZVOL {ds_options["name"]} with volsize {ds_options["volsize"]}')

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
                raise CallError(f'Failed to create or update raw file {path}: {cp.stderr}')

        return data

    async def _validate_device(self, device, old=None, update=True):
        svc_instance = await self.middleware.call(f'{self._service_type}.get_instance', device[self._service_type])
        device_adapter = self.device_factory.get_device_adapter(device)
        await self.middleware.run_in_thread(device_adapter.validate, old, svc_instance, update)
        return device

    async def _disk_choices(self):
        out = {}
        zvols = await self.middleware.call(
            'zfs.dataset.unlocked_zvols_fast', [
                ['OR', [['attachment', '=', None], ['attachment.method', '=', f'{self._service_type}.devices.query']]],
                ['ro', '=', False],
            ],
            {}, ['ATTACHMENT', 'RO']
        )

        for zvol in zvols:
            out[zvol['path']] = zvol['name']

        return out

    def _iotype_choices(self):
        return {key: key for key in IOTYPE_CHOICES}

    @private
    async def validate_path_field(self, verrors, schema, path):
        await check_path_resides_within_volume(verrors, self.middleware, schema, path)

    @private
    async def register_pylibvirt_device(self, device_key, device_klass, delegate_klass):
        self.device_factory.register(device_key, device_klass, delegate_klass)

    @private
    def get_pylibvirt_device(self, device_data):
        return self.device_factory.get_device(device_data)
