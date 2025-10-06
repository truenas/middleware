import copy
import errno
import os
import re
import subprocess

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceConvertArgs,
    VMDeviceConvertResult,
    VMDeviceCreateArgs,
    VMDeviceCreateResult,
    VMDeviceEntry,
    VMDeviceUpdateArgs,
    VMDeviceUpdateResult,
    VMDeviceDeleteArgs,
    VMDeviceDeleteResult,
    VMDeviceDiskChoicesArgs,
    VMDeviceDiskChoicesResult,
    VMDeviceIotypeChoicesArgs,
    VMDeviceIotypeChoicesResult,
    VMDeviceNicAttachChoicesArgs,
    VMDeviceNicAttachChoicesResult,
    VMDeviceBindChoicesArgs,
    VMDeviceBindChoicesResult,
)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import CallError, CRUDService, job, private
from middlewared.service_exception import ValidationError
from middlewared.utils import run

from .devices.storage_devices import IOTYPE_CHOICES
from .devices import DEVICES
from .utils import ACTIVE_STATES

VALID_DISK_FORMATS = ('qcow2', 'qed', 'raw', 'vdi', 'vhdx', 'vmdk')
RE_PPTDEV_NAME = re.compile(r'([0-9]+/){2}[0-9]+')


class VMDeviceModel(sa.Model):
    __tablename__ = 'vm_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    attributes = sa.Column(sa.JSON(encrypted=True))
    vm_id = sa.Column(sa.ForeignKey('vm_vm.id'), index=True)
    order = sa.Column(sa.Integer(), nullable=True)


class VMDeviceService(CRUDService):

    class Config:
        namespace = 'vm.device'
        datastore = 'vm.device'
        datastore_extend = 'vm.device.extend_device'
        cli_namespace = 'service.vm.device'
        role_prefix = 'VM_DEVICE'
        entry = VMDeviceEntry

    @private
    def run_convert_cmd(self, cmd_args, job, progress_desc):
        self.logger.info('Running command: %r', cmd_args)
        progress_pattern = re.compile(r'(\d+\.\d+)')
        try:
            with subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as process:
                stderr_data = []
                while True:
                    output = process.stdout.readline()
                    if not output and process.poll() is not None:
                        break

                    if output:
                        line = output.strip()
                        progress_match = progress_pattern.search(line)
                        if progress_match:
                            try:
                                progress_value = round(float(progress_match.group(1)))
                                job.set_progress(progress_value, progress_desc)
                            except ValueError:
                                self.logger.warning('Invalid progress value: %r', progress_match.group(1))
                        else:
                            self.logger.debug('qemu-img output: %r', line)

                remaining_stderr = process.stderr.read()
                if remaining_stderr:
                    stderr_data.append(remaining_stderr.strip())

                return_code = process.wait()
                if return_code != 0:
                    stderr_msg = '\n'.join(stderr_data) if stderr_data else 'No error details available'
                    raise CallError(f'qemu-img convert failed: {stderr_msg}', return_code)
        except (OSError, subprocess.SubprocessError) as e:
            raise CallError(f'Failed to execute qemu-img convert: {e}')

    @private
    def validate_convert_disk_image(self, dip, schema, converting_from_image_to_zvol=False):
        if not dip.startswith("/mnt/") or os.path.dirname(dip) == "/mnt":
            raise ValidationError(schema, f'{dip!r} is an invalid location', errno.EINVAL)

        st = None
        try:
            st = self.middleware.call_sync('filesystem.stat', dip)
            if converting_from_image_to_zvol:
                if st['type'] != 'FILE':
                    raise ValidationError(schema, f'{dip!r} is not a file', errno.EINVAL)

                vfs = self.middleware.call_sync('filesystem.statfs', dip)
                if has_internal_path(vfs['source']):
                    raise ValidationError(
                        schema,
                        f'{dip!r} is in a protected system path ({vfs["source"]})',
                        errno.EACCES
                    )
            else:
                # if converting from a zvol to a disk image,
                # qemu-img will create the file if it doesn't
                # exist OR it will OVERWRITE the file that exists
                raise ValidationError(
                    schema,
                    f'{dip!r} already exists and would be overwritten',
                    errno.EEXIST
                )
        except CallError as e:
            if e.errno == errno.ENOENT:
                if converting_from_image_to_zvol:
                    raise ValidationError(schema, f'{dip!r} does not exist', errno.ENOENT)
            else:
                raise e from None

        if not converting_from_image_to_zvol:
            sp = os.path.dirname(dip)
            try:
                dst = self.middleware.call_sync('filesystem.stat', os.path.dirname(sp))
                if dst['type'] != 'DIRECTORY':
                    raise ValidationError(schema, f'{sp!r} is not a directory', errno.EINVAL)

                vfs = self.middleware.call_sync('filesystem.statfs', dst['realpath'])
                if has_internal_path(vfs['source']):
                    raise ValidationError(
                        schema,
                        f'{sp!r} is in a protected system path ({vfs["source"]})',
                        errno.EACCES
                    )
            except CallError as e:
                if e.errno == errno.ENOENT:
                    raise ValidationError(schema, f'{sp!r} does not exist', errno.ENOENT)
                else:
                    raise e from None
        return st

    @private
    def validate_convert_zvol(self, zvp, schema):
        ptn = zvp.removeprefix('/dev/zvol/').replace('+', ' ')
        ntp = os.path.join('/dev/zvol', ptn.replace(' ', '+'))
        zv = self.middleware.call_sync(
            'zfs.resource.query_impl',
            {'paths': [ptn], 'properties': ['volsize']}
        )
        if not zv:
            raise ValidationError(schema, f'{ptn!r} does not exist', errno.ENOENT)
        elif zv[0]['type'] != 'VOLUME':
            raise ValidationError(schema, f'{ptn!r} is not a volume', errno.EINVAL)
        elif has_internal_path(ptn):
            raise ValidationError(schema, f'{ptn!r} is in a protected system path', errno.EACCES)
        elif not os.path.exists(ntp):
            raise ValidationError(schema, f'{ntp!r} does not exist', errno.ENOENT)

        return zv, ntp

    @api_method(
        VMDeviceConvertArgs,
        VMDeviceConvertResult,
        roles=['VM_DEVICE_WRITE']
    )
    @job(lock='vm.device.convert', lock_queue_size=1)
    def convert(self, job, data):
        """
        Convert between disk images and ZFS volumes. Supported disk image formats \
        are qcow2, qed, raw, vdi, vhdx, and vmdk. The conversion direction is determined \
        automatically based on file extension.
        """
        schema = 'vm.device.convert'
        # Determine conversion direction
        source_is_image = data['source'].endswith(VALID_DISK_FORMATS)
        dest_is_image = data['destination'].endswith(VALID_DISK_FORMATS)
        if (source_is_image and dest_is_image) or (not source_is_image and not dest_is_image):
            # could have provided the same value for source and destination
            # OR neither one of the fields specified are the disk image
            raise ValidationError(
                schema,
                'One path must be a disk image and the other must be a ZFS volume',
                errno.EINVAL
            )

        converting_from_image_to_zvol = False
        if source_is_image:
            schema += '.source'
            source_image = data['source']
            zvol = data['destination']
            converting_from_image_to_zvol = True
            progress_desc = "Convert to zvol progress"
        else:
            schema += '.destination'
            source_image = data['destination']
            zvol = data['source']
            progress_desc = "Convert to disk image progress"

        st = self.validate_convert_disk_image(source_image, schema, converting_from_image_to_zvol)
        zv, abs_zvolpath = self.validate_convert_zvol(zvol, schema)

        cmd_args = ['qemu-img', 'convert', '-p']
        if converting_from_image_to_zvol:
            if st and st['size'] > zv[0]['properties']['volsize']['value']:
                raise ValidationError(schema, f'{zvol!r} is too small', errno.ENOSPC)
            cmd_args.extend(['-O', 'raw', source_image, abs_zvolpath])
        else:
            dl = data['destination'].lower()
            for fmt in VALID_DISK_FORMATS:
                if dl.endswith(f'.{fmt}'):
                    cmd_args.extend(['-f', 'raw', '-O', fmt, abs_zvolpath, source_image])
                    break
            else:
                raise ValidationError(
                    schema,
                    f'Destination must have a valid format extension: {", ".join(VALID_DISK_FORMATS)}',
                    errno.EINVAL
                )

        self.run_convert_cmd(cmd_args, job, progress_desc)
        if not converting_from_image_to_zvol and st:
            # set the user/group owner to the uid/gid of the parent directory
            chown_job = self.middleware.call_sync(
                'filesystem.chown',
                {'path': data['destination'], 'uid': st['uid'], 'gid': st['gid']}
            )
            chown_job.wait_sync(raise_error=True)

        return True

    @api_method(VMDeviceDiskChoicesArgs, VMDeviceDiskChoicesResult, roles=['VM_DEVICE_READ'])
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

    @api_method(VMDeviceIotypeChoicesArgs, VMDeviceIotypeChoicesResult, roles=['VM_DEVICE_READ'])
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
            if device['attributes']['dtype'] == 'CDROM':
                device['order'] = 1000
            elif device['attributes']['dtype'] in ('DISK', 'RAW'):
                device['order'] = 1001
            else:
                device['order'] = 1002
        return device

    @api_method(VMDeviceNicAttachChoicesArgs, VMDeviceNicAttachChoicesResult, roles=['VM_DEVICE_READ'])
    def nic_attach_choices(self):
        """
        Available choices for NIC Attach attribute.
        """
        return self.middleware.call_sync('interface.choices', {'exclude': ['epair', 'tap', 'vnet']})

    @api_method(VMDeviceBindChoicesArgs, VMDeviceBindChoicesResult, roles=['VM_DEVICE_READ'])
    async def bind_choices(self):
        """
        Available choices for Bind attribute.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True, 'any': True, 'loopback': True}
            )
        }

    @private
    async def update_device(self, data, old=None):
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

    @api_method(VMDeviceCreateArgs, VMDeviceCreateResult)
    async def do_create(self, data):
        """
        Create a new device for the VM of id `vm`.

        If `attributes.dtype` is the `RAW` type and a new raw file is to be created, `attributes.exists` will be
        passed as false. This means the API handles creating the raw file and raises the appropriate exception if
        file creation fails.

        If `attributes.dtype` is of `DISK` type and a new Zvol is to be created, `attributes.create_zvol` will be
        passed as true with valid `attributes.zvol_name` and `attributes.zvol_volsize` values.
        """
        data = await self.validate_device(data, update=False)
        data = await self.update_device(data)

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data
        )
        await self.__reorder_devices(id_, data['vm'], data['order'])

        return await self.get_instance(id_)

    @api_method(VMDeviceUpdateArgs, VMDeviceUpdateResult)
    async def do_update(self, id_, data):
        """
        Update a VM device of `id`.

        Pass `attributes.size` to resize a `dtype` `RAW` device. The raw file will be resized.
        """
        device = await self.get_instance(id_)
        new = copy.deepcopy(device)
        new_attrs = data.pop('attributes', {})
        new.update(data)
        new['attributes'].update(new_attrs)

        new = await self.validate_device(new, device)
        new = await self.update_device(new, device)

        await self.middleware.call('datastore.update', self._config.datastore, id_, new)
        await self.__reorder_devices(id_, device['vm'], new['order'])

        return await self.get_instance(id_)

    @private
    async def delete_resource(self, options, device):
        device_dtype = device['attributes']['dtype']
        if options['zvol']:
            if device_dtype != 'DISK':
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
            if device_dtype != 'RAW':
                raise CallError('Device is not of RAW type.')
            try:
                os.unlink(device['attributes']['path'])
            except OSError:
                raise CallError(f'Failed to destroy {device["attributes"]["path"]}')

    @api_method(VMDeviceDeleteArgs, VMDeviceDeleteResult)
    async def do_delete(self, id_, options):
        """
        Delete a VM device of `id`.
        """
        device = await self.get_instance(id_)
        status = await self.middleware.call('vm.status', device['vm'])
        if status['state'] in ACTIVE_STATES:
            raise CallError('Please stop/resume associated VM before deleting VM device.')

        try:
            await self.delete_resource(options, device)
        except CallError:
            if not options['force']:
                raise

        return await self.middleware.call('datastore.delete', self._config.datastore, id_)

    async def __reorder_devices(self, id_, vm_id, order):
        if order is None:
            return
        filters = [('vm', '=', vm_id), ('id', '!=', id_)]
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
            return dev['attributes'].get('path') or zvol_name_to_path(dev['attributes']['zvol_name'])

        disks = [
            d for d in vm['devices']
            if d['attributes']['dtype'] in ('DISK', 'RAW', 'CDROM') and translate_device(d) == translate_device(device)
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
        device_obj = DEVICES[device['attributes']['dtype']](device, self.middleware)
        await self.middleware.run_in_thread(device_obj.validate, device, old, vm_instance, update)

        return device

    @private
    async def validate_display_devices(self, verrors, vm_instance):
        devs = await self.get_display_devices(vm_instance)
        if len(devs['spice']) > 1:
            verrors.add('attributes.type', 'Only one SPICE Display device is supported')
        if len(devs['vnc']) > 1:
            verrors.add('attributes.type', 'Only one VNC Display device is supported')

    @private
    async def get_display_devices(self, vm_instance):
        devs = {'spice': [], 'vnc': []}
        for dev in filter(lambda d: d['attributes']['dtype'] == 'DISPLAY', vm_instance['devices']):
            if dev['attributes']['type'] == 'SPICE':
                devs['spice'].append(dev)
            else:
                devs['vnc'].append(dev)
        return devs
