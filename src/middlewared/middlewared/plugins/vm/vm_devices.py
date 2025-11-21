import errno
import json
import math
import os
import re
import subprocess

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceBindChoicesArgs,
    VMDeviceBindChoicesResult,
    VMDeviceConvertArgs,
    VMDeviceConvertResult,
    VMDeviceCreateArgs,
    VMDeviceCreateResult,
    VMDeviceDeleteArgs,
    VMDeviceDeleteResult,
    VMDeviceDiskChoicesArgs,
    VMDeviceDiskChoicesResult,
    VMDeviceEntry,
    VMDeviceIotypeChoicesArgs,
    VMDeviceIotypeChoicesResult,
    VMDeviceNicAttachChoicesArgs,
    VMDeviceNicAttachChoicesResult,
    VMDeviceUpdateArgs,
    VMDeviceUpdateResult,
    VMDeviceVirtualSizeArgs,
    VMDeviceVirtualSizeResult,
)
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.service import CallError, CRUDService, job, private
from middlewared.service_exception import InstanceNotFound, ValidationError
from middlewared.utils.libvirt.device_factory import DeviceFactory
from middlewared.utils.libvirt.mixin import DeviceMixin


VALID_DISK_FORMATS = ('qcow2', 'qed', 'raw', 'vdi', 'vhdx', 'vmdk')
RE_PPTDEV_NAME = re.compile(r'([0-9]+/){2}[0-9]+')


class VMDeviceModel(sa.Model):
    __tablename__ = 'vm_device'

    id = sa.Column(sa.Integer(), primary_key=True)
    attributes = sa.Column(sa.JSON(encrypted=True))
    vm_id = sa.Column(sa.ForeignKey('vm_vm.id'), index=True)
    order = sa.Column(sa.Integer(), nullable=True)


class VMDeviceService(CRUDService, DeviceMixin):

    class Config:
        namespace = 'vm.device'
        datastore = 'vm.device'
        datastore_extend = 'vm.device.extend_device'
        cli_namespace = 'service.vm.device'
        role_prefix = 'VM_DEVICE'
        entry = VMDeviceEntry

    def __init__(self, *args, **kw):
        super(VMDeviceService, self).__init__(*args, **kw)
        self.device_factory = DeviceFactory(self.middleware)

    @property
    def _service_type(self):
        return 'vm'

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
    def virtual_size_impl(self, schema: str, file_path: str) -> int:
        if not os.path.isabs(file_path):
            raise ValidationError(schema, f'{file_path!r} must be an absolute path.', errno.EINVAL)

        try:
            rv = subprocess.run(
                ['qemu-img', 'info', '--output=json', file_path],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(rv.stdout)['virtual-size']
        except subprocess.CalledProcessError as e:
            raise ValidationError(schema, f'Failed to run command to determine virtual size: {e}')
        except KeyError:
            raise ValidationError(schema, f'Unable to determine virtual size of {file_path!r}: {rv.stdout}')
        except json.JSONDecodeError as e:
            raise ValidationError(schema, f'Failed to decode json output: {e}')

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

        for i in self.middleware.call_sync('vm.device.query', [['attributes.dtype', '=', 'DISK']]):
            vmzv = i['attributes'].get('path')
            if vmzv and vmzv == ntp:
                try:
                    vm = self.middleware.call_sync('vm.get_instance', i['vm'])
                    if vm['status']['state'] == 'RUNNING':
                        raise ValidationError(
                            schema,
                            f'{vmzv!r} is part of running VM. {vm["name"]!r} must be stopped first',
                            errno.EBUSY
                        )
                except InstanceNotFound:
                    pass

        return zv[0], ntp

    @api_method(
        VMDeviceVirtualSizeArgs,
        VMDeviceVirtualSizeResult,
        roles=['VM_DEVICE_READ']
    )
    def virtual_size(self, data):
        """
        Get the virtual size of a disk image using qemu-img info.

        Args:
            file_path: Absolute path to the disk image file

        Returns:
            Virtual size in bytes (int)

        Raise:
            ValidationError if any failure occurs
        """
        return self.virtual_size_impl('vm.device.virtual_size', data['path'])

    @api_method(
        VMDeviceConvertArgs,
        VMDeviceConvertResult,
        roles=['VM_DEVICE_WRITE'],
        audit='Converting disk image',
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
            virtual_size = self.virtual_size_impl(schema, st['realpath'])
            if virtual_size > zv['properties']['volsize']['value']:
                # always convert to next whole GB.
                vshgb = max(1, math.ceil(virtual_size / (1024 ** 3)))
                zvhgb = max(1, math.ceil(zv['properties']['volsize']['value'] / (1024 ** 3)))
                raise ValidationError(
                    schema,
                    f"{zv['name']} too small (~{zvhgb}G). Minimum size must be {vshgb}G",
                    errno.ENOSPC
                )
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
        return await self._disk_choices()

    @api_method(VMDeviceIotypeChoicesArgs, VMDeviceIotypeChoicesResult, roles=['VM_DEVICE_READ'])
    async def iotype_choices(self):
        """
        IO-type choices for storage devices.
        """
        return self._iotype_choices()

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

    @api_method(
        VMDeviceCreateArgs, VMDeviceCreateResult,
        audit='VM device create',
        audit_extended=lambda data: f'{data["attributes"]["dtype"]}',
    )
    async def do_create(self, data):
        """
        Create a new device for the VM of id `vm`.

        If `attributes.dtype` is the `RAW` type and a new raw file is to be created, `attributes.exists` will be
        passed as false. This means the API handles creating the raw file and raises the appropriate exception if
        file creation fails.

        If `attributes.dtype` is of `DISK` type and a new Zvol is to be created, `attributes.create_zvol` will be
        passed as true with valid `attributes.zvol_name` and `attributes.zvol_volsize` values.
        """
        return await self._create_impl(data)

    @api_method(
        VMDeviceUpdateArgs, VMDeviceUpdateResult,
        audit='VM device update',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update a VM device of `id`.

        Pass `attributes.size` to resize a `dtype` `RAW` device. The raw file will be resized.
        """
        return await self._update_impl(id_, data, audit_callback)

    @api_method(
        VMDeviceDeleteArgs, VMDeviceDeleteResult,
        audit='VM device delete',
        audit_callback=True,
    )
    async def do_delete(self, audit_callback, id_, options):
        """
        Delete a VM device of `id`.
        """
        return await self._delete_impl(id_, options, audit_callback)

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
