import errno
import os

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Error, Int, Patch, Str
from middlewared.service import CallError, CRUDService, private, ValidationErrors
from middlewared.utils import osc, run
from middlewared.async_validators import check_path_resides_within_volume

from .devices import CDROM, DISK, NIC, PCI, RAW, VNC


class VMDeviceModel(sa.Model):
    __tablename__ = 'vm_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    dtype = sa.Column(sa.String(50))
    attributes = sa.Column(sa.JSON())
    vm_id = sa.Column(sa.ForeignKey('vm_vm.id'), index=True)
    order = sa.Column(sa.Integer(), nullable=True)


class VMDeviceService(CRUDService):

    DEVICE_ATTRS = {
        'CDROM': CDROM.schema,
        'RAW': RAW.schema,
        'DISK': DISK.schema,
        'NIC': NIC.schema,
        'PCI': PCI.schema,
        'VNC': VNC.schema,
    }

    class Config:
        namespace = 'vm.device'
        datastore = 'vm.device'
        datastore_extend = 'vm.device.extend_device'

    @private
    async def create_resource(self, device, old=None):
        return (
            (device['dtype'] == 'DISK' and device['attributes'].get('create_zvol')) or (
                device['dtype'] == 'RAW' and (not device['attributes'].get('exists', True) or (
                    old and old['attributes'].get('size') != device['attributes'].get('size')
                ))
            )
        )

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
    def nic_attach_choices(self):
        """
        Available choices for NIC Attach attribute.
        """
        return self.middleware.call_sync('interface.choices', {'exclude': ['epair', 'tap', 'vnet']})

    @accepts()
    def vnc_bind_choices(self):
        """
        Available choices for VNC Bind attribute.
        """
        return {
            i['address']: i['address']
            for i in self.middleware.call_sync('interface.ip_in_use', {'any': True, 'loopback': True})
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
            Str('dtype', enum=['NIC', 'DISK', 'CDROM', 'PCI', 'VNC', 'RAW'],
                required=True),
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
        data = await self.validate_device(data)
        data = await self.update_device(data)

        id = await self.middleware.call(
            'datastore.insert', self._config.datastore, data
        )
        await self.__reorder_devices(id, data['vm'], data['order'])

        return await self.get_instance(id)

    @accepts(Int('id'), Patch(
        'vmdevice_create',
        'vmdevice_update',
        ('attr', {'update': True}),
    ))
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
            zvol_id = device['attributes'].get('path', '').rsplit('/dev/zvol/')[-1]
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
        )
    )
    async def do_delete(self, id, options):
        """
        Delete a VM device of `id`.
        """
        await self.delete_resource(options, await self.get_instance(id))
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
    async def validate_device(self, device, old=None, vm_instance=None):
        # We allow vm_instance to be passed for cases where VM devices are being updated via VM and
        # the device checks should be performed with the modified vm_instance object not the one db holds
        # vm_instance should be provided at all times when handled by VMService, if VMDeviceService is interacting,
        # then it means the device is configured with a VM and we can retrieve the VM's data from db
        if not vm_instance:
            vm_instance = await self.middleware.call('vm.get_instance', device['vm'])

        verrors = ValidationErrors()
        schema = self.DEVICE_ATTRS.get(device['dtype'])
        if schema:
            try:
                device['attributes'] = schema.clean(device['attributes'])
            except Error as e:
                verrors.add(f'attributes.{e.attribute}', e.errmsg, e.errno)

            try:
                schema.validate(device['attributes'])
            except ValidationErrors as e:
                verrors.extend(e)

            if verrors:
                raise verrors

        # vm_instance usages SHOULD NOT rely on device `id` field to uniquely identify objects as it's possible
        # VMService is creating a new VM with devices and the id's don't exist yet

        if device.get('dtype') == 'DISK':
            create_zvol = device['attributes'].get('create_zvol')
            path = device['attributes'].get('path')
            if create_zvol:
                for attr in ('zvol_name', 'zvol_volsize'):
                    if not device['attributes'].get(attr):
                        verrors.add(f'attributes.{attr}', 'This field is required.')
                parentzvol = (device['attributes'].get('zvol_name') or '').rsplit('/', 1)[0]
                if parentzvol and not await self.middleware.call('pool.dataset.query', [('id', '=', parentzvol)]):
                    verrors.add(
                        'attributes.zvol_name',
                        f'Parent dataset {parentzvol} does not exist.', errno.ENOENT
                    )
                zvol = await self.middleware.call(
                    'pool.dataset.query', [['id', '=', device['attributes'].get('zvol_name')]]
                )
                if not verrors and create_zvol and zvol:
                    verrors.add(
                        'attributes.zvol_name', f'{device["attributes"]["zvol_name"]} already exists.'
                    )
                elif zvol and zvol[0]['locked']:
                    verrors.add('attributes.zvol_name', f'{zvol[0]["id"]} is locked.')
            elif not path:
                verrors.add('attributes.path', 'Disk path is required.')
            elif path and not os.path.exists(path):
                verrors.add('attributes.path', f'Disk path {path} does not exist.', errno.ENOENT)

            if path and len(path) > 63:
                # SPECNAMELEN is not long enough (63) in 12, 13 will be 255
                verrors.add(
                    'attributes.path',
                    f'Disk path {path} is too long, reduce to less than 63 characters', errno.ENAMETOOLONG
                )
            if not await self.disk_uniqueness_integrity_check(device, vm_instance):
                verrors.add(
                    'attributes.path',
                    f'{vm_instance["name"]} has "{path}" already configured'
                )
        elif device.get('dtype') == 'RAW':
            path = device['attributes'].get('path')
            exists = device['attributes'].get('exists', True)
            if not path:
                verrors.add('attributes.path', 'Path is required.')
            else:
                if exists and not os.path.exists(path):
                    verrors.add('attributes.path', 'Path must exist.')
                if not exists:
                    if os.path.exists(path):
                        verrors.add('attributes.path', 'Path must not exist.')
                    elif not device['attributes'].get('size'):
                        verrors.add('attributes.size', 'Please provide a valid size for the raw file.')
                if (
                    old and old['attributes'].get('size') != device['attributes'].get('size') and
                    not device['attributes'].get('size')
                ):
                    verrors.add('attributes.size', 'Please provide a valid size for the raw file.')
                await check_path_resides_within_volume(
                    verrors, self.middleware, 'attributes.path', path,
                )
                if not await self.disk_uniqueness_integrity_check(device, vm_instance):
                    verrors.add(
                        'attributes.path',
                        f'{vm_instance["name"]} has "{path}" already configured'
                    )
        elif device.get('dtype') == 'CDROM':
            path = device['attributes'].get('path')
            if not path:
                verrors.add('attributes.path', 'Path is required.')
            elif not os.path.exists(path):
                verrors.add('attributes.path', f'Unable to locate CDROM device at {path}')
            elif not await self.disk_uniqueness_integrity_check(device, vm_instance):
                verrors.add('attributes.path', f'{vm_instance["name"]} has "{path}" already configured')
        elif device.get('dtype') == 'NIC':
            nic = device['attributes'].get('nic_attach')
            if nic:
                nic_choices = await self.middleware.call('vm.device.nic_attach_choices')
                if nic not in nic_choices:
                    verrors.add('attributes.nic_attach', 'Not a valid choice.')
            await self.failover_nic_check(device, verrors, 'attributes')
        elif device.get('dtype') == 'PCI':
            if device['attributes'].get('pptdev') not in await self.middleware.call('vm.device.pptdev_choices'):
                verrors.add('attribute.pptdev', 'Not a valid choice. The PCI device is not available for passthru.')
            if (await self.middleware.call('vm.device.get_iommu_type')) is None:
                verrors.add('attribute.pptdev', 'IOMMU support is required.')
        elif device.get('dtype') == 'VNC':
            if vm_instance:
                if osc.IS_FREEBSD and vm_instance['bootloader'] != 'UEFI':
                    verrors.add('dtype', 'VNC only works with UEFI bootloader.')
                if all(not d.get('id') for d in vm_instance['devices']):
                    # VM is being created so devices don't have an id yet. We can just count no of VNC devices
                    # and add a validation error if it's more then one
                    if len([d for d in vm_instance['devices'] if d['dtype'] == 'VNC']) > 1:
                        verrors.add('dtype', 'Only one VNC device is allowed per VM')
                elif any(d['dtype'] == 'VNC' and d['id'] != device.get('id') for d in vm_instance['devices']):
                    verrors.add('dtype', 'Only one VNC device is allowed per VM')
            all_ports = [
                d['attributes'].get('vnc_port')
                for d in (await self.middleware.call('vm.device.query', [['dtype', '=', 'VNC']]))
                if d['id'] != device.get('id')
            ]
            if device['attributes'].get('vnc_port'):
                if device['attributes']['vnc_port'] in all_ports:
                    verrors.add('attributes.vnc_port', 'Specified vnc port is already in use')
            else:
                device['attributes']['vnc_port'] = (await self.middleware.call('vm.vnc_port_wizard'))['vnc_port']

        if device['dtype'] in ('RAW', 'DISK') and device['attributes'].get('physical_sectorsize')\
                and not device['attributes'].get('logical_sectorsize'):
            verrors.add(
                'attributes.logical_sectorsize',
                'This field must be provided when physical_sectorsize is specified.'
            )

        if verrors:
            raise verrors

        return device

    @private
    async def failover_nic_check(self, vm_device, verrors, schema):
        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.licensed'):
            nics = await self.middleware.call('vm.device.nic_capability_checks', [vm_device])
            if nics:
                verrors.add(
                    f'{schema}.nic_attach',
                    f'Capabilities must be disabled for {",".join(nics)} interface '
                    'in Network->Interfaces section before using this device with VM.'
                )
