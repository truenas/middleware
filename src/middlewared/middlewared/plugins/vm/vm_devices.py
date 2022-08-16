import os
import re

import middlewared.sqlalchemy as sa

from middlewared.plugins.vm.devices.storage_devices import IOTYPE_CHOICES
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.schema import accepts, Bool, Dict, Int, Patch, returns, Str
from middlewared.service import CallError, CRUDService, private
from middlewared.utils import run
from middlewared.async_validators import check_path_resides_within_volume

from .devices import CDROM, DISK, NIC, PCI, RAW, DISPLAY, USB
from .utils import ACTIVE_STATES


RE_PPTDEV_NAME = re.compile(r'([0-9]+/){2}[0-9]+')


class VMDeviceModel(sa.Model):
    __tablename__ = 'vm_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    dtype = sa.Column(sa.String(50))
    attributes = sa.Column(sa.JSON())
    vm_id = sa.Column(sa.ForeignKey('vm_vm.id'), index=True)
    order = sa.Column(sa.Integer(), nullable=True)


class VMDeviceService(CRUDService):

    DEVICES = {
        'CDROM': CDROM,
        'RAW': RAW,
        'DISK': DISK,
        'NIC': NIC,
        'PCI': PCI,
        'DISPLAY': DISPLAY,
        'USB': USB,
    }

    ENTRY = Patch(
        'vmdevice_create', 'vm_device_entry',
        ('add', Int('id')),
    )

    class Config:
        namespace = 'vm.device'
        datastore = 'vm.device'
        datastore_extend = 'vm.device.extend_device'
        cli_namespace = 'service.vm.device'

    @accepts()
    @returns(Dict(additional_attrs=True, example={'vms/test 1': '/dev/zvol/vms/test+1'}))
    async def disk_choices(self):
        """
        Returns disk choices for device type "DISK".
        """
        out = {}
        zvols = await self.middleware.call(
            'zfs.dataset.unlocked_zvols_fast', [
                ['OR', [['attachment', '=', None], ['attachment.method', '=', 'vm.devices.query']]],
                ['ro', '=', False],
            ],
            {}, ['ATTACHMENT', 'RO']
        )

        for zvol in zvols:
            out[zvol['path']] = zvol['name']

        return out

    @accepts()
    @returns(Dict(
        *[Str(k, enum=[k]) for k in IOTYPE_CHOICES]
    ))
    async def iotype_choices(self):
        """
        IO-type choices for storage devices.
        """
        return {k: k for k in IOTYPE_CHOICES}

    @private
    async def extend_device(self, device):
        if device['vm']:
            device['vm'] = device['vm']['id']
        if not device['order']:
            if device['dtype'] == 'CDROM':
                device['order'] = 1000
            elif device['dtype'] in ('DISK', 'RAW'):
                device['order'] = 1001
            else:
                device['order'] = 1002
        return device

    @accepts()
    @returns(Dict(additional_attrs=True))
    def nic_attach_choices(self):
        """
        Available choices for NIC Attach attribute.
        """
        return self.middleware.call_sync('interface.choices', {'exclude': ['epair', 'tap', 'vnet']})

    @accepts()
    @returns(Dict(additional_attrs=True))
    async def bind_choices(self):
        """
        Available choices for Bind attribute.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True, 'any': True}
            )
        }

    @private
    async def update_device(self, data, old=None):
        if data['dtype'] == 'DISK':
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

                new_zvol = (await self.middleware.call('pool.dataset.create', ds_options))['id']
                data['attributes']['path'] = f'/dev/zvol/{new_zvol}'
        elif data['dtype'] == 'RAW' and (
            not data['attributes'].pop('exists', True) or (
                old and old['attributes']['size'] != data['attributes']['size']
            )
        ):
            path = data['attributes']['path']
            cp = await run(['truncate', '-s', str(data['attributes']['size']), path], check=False)
            if cp.returncode:
                raise CallError(f'Failed to create or update raw file {path}: {cp.stderr}')

        return data

    @accepts(
        Dict(
            'vmdevice_create',
            Str('dtype', enum=['NIC', 'DISK', 'CDROM', 'PCI', 'DISPLAY', 'RAW', 'USB'], required=True),
            Int('vm', required=True),
            Dict('attributes', additional_attrs=True, default=None),
            Int('order', default=None, null=True),
            register=True,
        ),
    )
    async def do_create(self, data):
        """
        Create a new device for the VM of id `vm`.

        If `dtype` is the `RAW` type and a new raw file is to be created, `attributes.exists` will be passed as false.
        This means the API handles creating the raw file and raises the appropriate exception if file creation fails.

        If `dtype` is of `DISK` type and a new Zvol is to be created, `attributes.create_zvol` will be passed as
        true with valid `attributes.zvol_name` and `attributes.zvol_volsize` values.
        """
        data = await self.validate_device(data, update=False)
        data = await self.update_device(data)

        id = await self.middleware.call(
            'datastore.insert', self._config.datastore, data
        )
        await self.__reorder_devices(id, data['vm'], data['order'])

        return await self.get_instance(id)

    async def do_update(self, id, data):
        """
        Update a VM device of `id`.

        Pass `attributes.size` to resize a `dtype` `RAW` device. The raw file will be resized.
        """
        device = await self.get_instance(id)
        new = device.copy()
        new.update(data)

        new = await self.validate_device(new, device)
        new = await self.update_device(new, device)

        await self.middleware.call('datastore.update', self._config.datastore, id, new)
        await self.__reorder_devices(id, device['vm'], new['order'])

        return await self.get_instance(id)

    @private
    async def delete_resource(self, options, device):
        if options['zvol']:
            if device['dtype'] != 'DISK':
                raise CallError('The device is not a disk and has no zvol to destroy.')
            if not device['attributes'].get('path', '').startswith('/dev/zvol'):
                raise CallError('Unable to destroy zvol as disk device has misconfigured path')
            zvol_id = zvol_path_to_name(device['attributes']['path'])
            if await self.middleware.call('pool.dataset.query', [['id', '=', zvol_id]]):
                # FIXME: We should use pool.dataset.delete but right now FS attachments will consider
                # the current device as a valid reference. Also should we stopping the vm only when deleting an
                # attachment ?
                await self.middleware.call('zfs.dataset.delete', zvol_id)
        if options['raw_file']:
            if device['dtype'] != 'RAW':
                raise CallError('Device is not of RAW type.')
            try:
                os.unlink(device['attributes']['path'])
            except OSError:
                raise CallError(f'Failed to destroy {device["attributes"]["path"]}')

    @accepts(
        Int('id'),
        Dict(
            'vm_device_delete',
            Bool('zvol', default=False),
            Bool('raw_file', default=False),
            Bool('force', default=False),
        )
    )
    async def do_delete(self, id, options):
        """
        Delete a VM device of `id`.
        """
        device = await self.get_instance(id)
        status = await self.middleware.call('vm.status', device['vm'])
        if status['state'] in ACTIVE_STATES:
            raise CallError('Please stop/resume associated VM before deleting VM device.')

        try:
            await self.delete_resource(options, device)
        except CallError:
            if not options['force']:
                raise

        if device['dtype'] == 'PCI':
            device_obj = PCI(device, middleware=self.middleware)
            if await self.middleware.run_in_thread(device_obj.safe_to_reattach):
                try:
                    await self.middleware.run_in_thread(device_obj.reattach_device)
                except CallError:
                    if not options['force']:
                        raise

        return await self.middleware.call('datastore.delete', self._config.datastore, id)

    async def __reorder_devices(self, id, vm_id, order):
        if order is None:
            return
        filters = [('vm', '=', vm_id), ('id', '!=', id)]
        if await self.middleware.call('vm.device.query', filters + [('order', '=', order)]):
            used_order = [order]
            for device in await self.middleware.call('vm.device.query', filters, {'order_by': ['order']}):
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

    @private
    async def disk_uniqueness_integrity_check(self, device, vm):
        # This ensures that the disk is not already present for `vm`
        def translate_device(dev):
            # A disk should have a path configured at all times, when that is not the case, that means `dtype` is DISK
            # and end user wants to create a new zvol in this case.
            return dev['attributes'].get('path') or f'/dev/zvol/{dev["attributes"]["zvol_name"]}'

        disks = [
            d for d in vm['devices']
            if d['dtype'] in ('DISK', 'RAW', 'CDROM') and translate_device(d) == translate_device(device)
        ]
        if not disks:
            # We don't have that disk path in vm devices, we are good to go
            return True
        elif len(disks) > 1:
            # VM is mis-configured
            return False
        elif not device.get('id') and disks:
            # A new device is being created, however it already exists in vm. This can also happen when VM instance
            # is being created, in that case it's okay. Key here is that we won't have the id field present
            return not bool(disks[0].get('id'))
        elif device.get('id'):
            # The device is being updated, if the device is same as we have in db, we are okay
            return device['id'] == disks[0].get('id')
        else:
            return False

    @private
    async def validate_path_field(self, verrors, schema, path):
        await check_path_resides_within_volume(verrors, self.middleware, schema, path)

    @private
    async def validate_device(self, device, old=None, update=True):
        vm_instance = await self.middleware.call('vm.get_instance', device['vm'])
        device_obj = self.DEVICES[device['dtype']](device, self.middleware)
        await self.middleware.run_in_thread(device_obj.validate, device, old, vm_instance, update)

        return device

    @private
    async def validate_display_devices(self, verrors, vm_instance):
        devs = await self.get_display_devices(vm_instance)
        if len(devs['vnc']) > 1:
            verrors.add('attributes.type', 'Only one VNC Display device is supported')
        if len(devs['spice']) > 1:
            verrors.add('attributes.type', 'Only one SPICE Display device is supported')

    @private
    async def get_display_devices(self, vm_instance):
        devs = {'vnc': [], 'spice': []}
        for dev in filter(lambda d: d['dtype'] == 'DISPLAY', vm_instance['devices']):
            if dev['attributes']['type'] == 'SPICE':
                devs['spice'].append(dev)
            else:
                devs['vnc'].append(dev)
        return devs
