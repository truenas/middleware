import asyncio
import errno
import functools
import os
import re
import shlex
import uuid

import middlewared.sqlalchemy as sa

from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Path, returns, Str, ValidationErrors
from middlewared.service import CallError, CRUDService, item_method, private
from middlewared.validators import Range, UUID
from middlewared.plugins.vm.numeric_set import parse_numeric_set, NumericSet

from .utils import ACTIVE_STATES, LIBVIRT_USER
from .vm_supervisor import VMSupervisorMixin


BOOT_LOADER_OPTIONS = {
    'UEFI': 'UEFI',
    'UEFI_CSM': 'Legacy BIOS',
}
LIBVIRT_LOCK = asyncio.Lock()
RE_NAME = re.compile(r'^[a-zA-Z_0-9]+$')


class VMModel(sa.Model):
    __tablename__ = 'vm_vm'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(150))
    description = sa.Column(sa.String(250))
    vcpus = sa.Column(sa.Integer(), default=1)
    memory = sa.Column(sa.Integer())
    min_memory = sa.Column(sa.Integer(), nullable=True)
    autostart = sa.Column(sa.Boolean(), default=False)
    time = sa.Column(sa.String(5), default='LOCAL')
    bootloader = sa.Column(sa.String(50), default='UEFI')
    cores = sa.Column(sa.Integer(), default=1)
    threads = sa.Column(sa.Integer(), default=1)
    hyperv_enlightenments = sa.Column(sa.Boolean(), default=False)
    shutdown_timeout = sa.Column(sa.Integer(), default=90)
    cpu_mode = sa.Column(sa.Text())
    cpu_model = sa.Column(sa.Text(), nullable=True)
    cpuset = sa.Column(sa.Text(), default=None, nullable=True)
    nodeset = sa.Column(sa.Text(), default=None, nullable=True)
    pin_vcpus = sa.Column(sa.Boolean(), default=False)
    hide_from_msr = sa.Column(sa.Boolean(), default=False)
    suspend_on_snapshot = sa.Column(sa.Boolean(), default=False)
    ensure_display_device = sa.Column(sa.Boolean(), default=True)
    arch_type = sa.Column(sa.String(255), default=None, nullable=True)
    machine_type = sa.Column(sa.String(255), default=None, nullable=True)
    uuid = sa.Column(sa.String(255))
    command_line_args = sa.Column(sa.Text(), default='', nullable=False)
    bootloader_ovmf = sa.Column(sa.String(1024), default='OVMF_CODE.fd')
    trusted_platform_module = sa.Column(sa.Boolean(), default=False)
    nvram_location = sa.Column(sa.Text(), default=None, nullable=True)


@functools.cache
def ovmf_options():
    return [path for path in os.listdir('/usr/share/OVMF') if re.findall(r'^OVMF_CODE.*.fd', path)]


class VMService(CRUDService, VMSupervisorMixin):

    class Config:
        namespace = 'vm'
        datastore = 'vm.vm'
        datastore_extend = 'vm.extend_vm'
        datastore_extend_context = 'vm.extend_context'
        cli_namespace = 'service.vm'
        role_prefix = 'VM'

    ENTRY = Patch(
        'vm_create',
        'vm_entry',
        ('add', List('devices')),
        ('add', Dict(
            'status',
            Str('state', required=True),
            Int('pid', null=True, required=True),
            Str('domain_state', required=True),
        )),
        ('add', Bool('display_available')),
        ('add', Int('id')),
    )

    @accepts(roles=['VM_READ'])
    @returns(Dict(additional_attrs=True))
    def bootloader_ovmf_choices(self):
        """
        Retrieve bootloader ovmf choices
        """
        return {path: path for path in ovmf_options()}

    @private
    def extend_context(self, rows, extra):
        status = {}
        if rows:
            self._check_setup_connection()
        for row in rows:
            status[row['id']] = self.status_impl(row)

        return {
            'status': status,
        }

    @accepts(roles=['VM_READ'])
    @returns(Dict(
        *[Str(k, enum=[v]) for k, v in BOOT_LOADER_OPTIONS.items()],
    ))
    async def bootloader_options(self):
        """
        Supported motherboard firmware options.
        """
        return BOOT_LOADER_OPTIONS

    @private
    async def extend_vm(self, vm, context):
        vm['devices'] = await self.middleware.call(
            'vm.device.query',
            [('vm', '=', vm['id'])],
            {'force_sql_filters': True},
        )
        vm['display_available'] = any(device['dtype'] == 'DISPLAY' for device in vm['devices'])
        vm['status'] = context['status'][vm['id']]
        return vm

    @accepts(Dict(
        'vm_create',
        Str('command_line_args', default=''),
        Str('cpu_mode', default='CUSTOM', enum=[
            'CUSTOM', 'HOST-MODEL', 'HOST-PASSTHROUGH']),
        Str('cpu_model', default=None, null=True),
        Str('name', required=True),
        Str('description'),
        Int('vcpus', default=1),
        Int('cores', default=1),
        Int('threads', default=1),
        Str('cpuset', default=None, null=True, validators=[NumericSet()]),
        Str('nodeset', default=None, null=True, validators=[NumericSet()]),
        Bool('pin_vcpus', default=False),
        Bool('suspend_on_snapshot', default=False),
        Bool('trusted_platform_module', default=False),
        Int('memory', required=True, validators=[Range(min_=20)]),
        Int('min_memory', null=True, validators=[Range(min_=20)], default=None),
        Bool('hyperv_enlightenments', default=False),
        Str('bootloader', enum=list(BOOT_LOADER_OPTIONS.keys()), default='UEFI'),
        Str('bootloader_ovmf', default='OVMF_CODE.fd'),
        Bool('autostart', default=True),
        Bool('hide_from_msr', default=False),
        Bool('ensure_display_device', default=True),
        Str('time', enum=['LOCAL', 'UTC'], default='LOCAL'),
        Int('shutdown_timeout', default=90,
            validators=[Range(min_=5, max_=300)]),
        Str('arch_type', null=True, default=None),
        Str('machine_type', null=True, default=None),
        Str('uuid', null=True, default=None, validators=[UUID()]),
        Path('nvram_location', null=True, default=None),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create a Virtual Machine (VM).

        Maximum of 16 guest virtual CPUs are allowed. By default, every virtual CPU is configured as a
        separate package. Multiple cores can be configured per CPU by specifying `cores` attributes.
        `vcpus` specifies total number of CPU sockets. `cores` specifies number of cores per socket. `threads`
        specifies number of threads per core.

        `ensure_display_device` when set ( the default ) will ensure that the guest always has access to a video device.
        For headless installations like ubuntu server this is required for the guest to operate properly. However
        for cases where consumer would like to use GPU passthrough and does not want a display device added should set
        this to `false`.

        `arch_type` refers to architecture type and can be specified for the guest. By default the value is `null` and
        system in this case will choose a reasonable default based on host.

        `machine_type` refers to machine type of the guest based on the architecture type selected with `arch_type`.
        By default the value is `null` and system in this case will choose a reasonable default based on `arch_type`
        configuration.

        `shutdown_timeout` indicates the time in seconds the system waits for the VM to cleanly shutdown. During system
        shutdown, if the VM hasn't exited after a hardware shutdown signal has been sent by the system within
        `shutdown_timeout` seconds, system initiates poweroff for the VM to stop it.

        `hide_from_msr` is a boolean which when set will hide the KVM hypervisor from standard MSR based discovery and
        is useful to enable when doing GPU passthrough.

        `hyperv_enlightenments` can be used to enable subset of predefined Hyper-V enlightenments for Windows guests.
        These enlightenments improve performance and enable otherwise missing features.

        `suspend_on_snapshot` is a boolean attribute which when enabled will automatically pause/suspend VMs when
        a snapshot is being taken for periodic snapshot tasks. For manual snapshots, if user has specified vms to
        be paused, they will be in that case.

        `nvram_location` is a path field which holds NVRAM file used by guest to boot in UEFI mode. This is a required
        field when guest is to be booted with UEFI.
        """
        async with LIBVIRT_LOCK:
            await self.middleware.run_in_thread(self._check_setup_connection)

        verrors = ValidationErrors()
        await self.common_validation(verrors, 'vm_create', data)
        verrors.check()

        vm_id = await self.middleware.call('datastore.insert', 'vm.vm', data)
        await self.middleware.run_in_thread(self._add, vm_id)
        await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(vm_id)

    @private
    async def common_validation(self, verrors, schema_name, data, old=None):
        if data['bootloader_ovmf'] not in await self.middleware.call('vm.bootloader_ovmf_choices'):
            verrors.add(
                f'{schema_name}.bootloader_ovmf',
                'Invalid bootloader ovmf choice specified'
            )

        if data['bootloader'] == 'UEFI' and not data['nvram_location']:
            verrors.add(
                f'{schema_name}.nvram_location',
                'NVRAM location must be specified when booting with UEFI'
            )

        if data['nvram_location'] and await self.middleware.run_in_thread(
            os.path.exists, data['nvram_location']
        ) and not await self.middleware.call(
            'filesystem.can_access_as_user', LIBVIRT_USER, data['nvram_location'], {'read': True, 'write': True}
        ):
            # It is fine if the file does not exist as libvirt will create it
            # However we do want to ensure that if it does exist, libvirt user is able to read/write to it
            verrors.add(
                f'{schema_name}.nvram_location',
                'Libvirt user is not able to read the specified NVRAM file'
            )

        if not data.get('uuid'):
            data['uuid'] = str(uuid.uuid4())

        if not await self.middleware.call('vm.license_active'):
            verrors.add(
                f'{schema_name}.name',
                'System is not licensed to use VMs'
            )

        if data['min_memory'] and data['min_memory'] > data['memory']:
            verrors.add(
                f'{schema_name}.min_memory',
                'Minimum memory should not be greater than defined/maximum memory'
            )

        try:
            shlex.split(data['command_line_args'])
        except ValueError as e:
            verrors.add(
                f'{schema_name}.command_line_args',
                f'Parse error: {e.args[0]}'
            )

        vcpus = data['vcpus'] * data['cores'] * data['threads']
        if vcpus:
            flags = await self.middleware.call('vm.flags')
            max_vcpus = await self.middleware.call('vm.maximum_supported_vcpus')
            if vcpus > max_vcpus:
                verrors.add(
                    f'{schema_name}.vcpus',
                    f'Maximum {max_vcpus} vcpus are supported.'
                    f'Please ensure the product of "{schema_name}.vcpus", "{schema_name}.cores" and '
                    f'"{schema_name}.threads" is less then {max_vcpus}.'
                )
            elif flags['intel_vmx']:
                if vcpus > 1 and flags['unrestricted_guest'] is False:
                    verrors.add(
                        f'{schema_name}.vcpus', 'Only one Virtual CPU is allowed in this system.')
            elif flags['amd_rvi']:
                if vcpus > 1 and flags['amd_asids'] is False:
                    verrors.add(
                        f'{schema_name}.vcpus', 'Only one virtual CPU is allowed in this system.'
                    )
            elif not await self.middleware.call('vm.supports_virtualization'):
                verrors.add(
                    schema_name, 'This system does not support virtualization.'
                )

        if data.get('arch_type') or data.get('machine_type'):
            choices = await self.middleware.call('vm.guest_architecture_and_machine_choices')
            if data.get('arch_type') and data['arch_type'] not in choices:
                verrors.add(f'{schema_name}.arch_type',
                            'Specified architecture type is not supported on this system')
            if data.get('machine_type'):
                if not data.get('arch_type'):
                    verrors.add(
                        f'{schema_name}.arch_type', f'Must be specified when "{schema_name}.machine_type" is set'
                    )
                elif data['arch_type'] in choices and data['machine_type'] not in choices[data['arch_type']]:
                    verrors.add(
                        f'{schema_name}.machine_type',
                        f'Specified machine type is not supported for {choices[data["arch_type"]]!r} architecture type'
                    )

        if data.get('cpu_mode') != 'CUSTOM' and data.get('cpu_model'):
            verrors.add(
                f'{schema_name}.cpu_model',
                'This attribute should not be specified when "cpu_mode" is not "CUSTOM".'
            )
        elif data.get('cpu_model') and data['cpu_model'] not in await self.middleware.call('vm.cpu_model_choices'):
            verrors.add(f'{schema_name}.cpu_model',
                        'Please select a valid CPU model.')

        if 'name' in data:
            filters = [('name', '=', data['name'])]
            if old:
                filters.append(('id', '!=', old['id']))
            if await self.middleware.call('vm.query', filters):
                verrors.add(
                    f'{schema_name}.name',
                    'This name already exists.', errno.EEXIST
                )
            elif not RE_NAME.search(data['name']):
                verrors.add(
                    f'{schema_name}.name',
                    'Only alphanumeric characters are allowed.'
                )

        if data['pin_vcpus']:
            if not data['cpuset']:
                verrors.add(
                    f'{schema_name}.cpuset',
                    f'Must be specified when "{schema_name}.pin_vcpus" is set.'
                )
            elif len(parse_numeric_set(data['cpuset'])) != vcpus:
                verrors.add(
                    f'{schema_name}.pin_vcpus',
                    f'Number of cpus in "{schema_name}.cpuset" must be equal to total number vpcus if pinning is enabled.'
                )

        # TODO: Let's please implement PCI express hierarchy as the limit on devices in KVM is quite high
        # with reports of users having thousands of disks
        # Let's validate that the VM has the correct no of slots available to accommodate currently configured devices

    @accepts(
        Int('id', required=True),
        Patch(
            'vm_entry',
            'vm_update',
            ('rm', {'name': 'devices'}),
            ('rm', {'name': 'display_available'}),
            ('rm', {'name': 'status'}),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, id_, data):
        """
        Update all information of a specific VM.

        `devices` is a list of virtualized hardware to attach to the virtual machine. If `devices` is not present,
        no change is made to devices. If either the device list order or data stored by the device changes when the
        attribute is passed, these actions are taken:

        1) If there is no device in the `devices` list which was previously attached to the VM, that device is
           removed from the virtual machine.
        2) Devices are updated in the `devices` list when they contain a valid `id` attribute that corresponds to
           an existing device.
        3) Devices that do not have an `id` attribute are created and attached to `id` VM.
        """

        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        if new['name'] != old['name']:
            await self.middleware.run_in_thread(self._check_setup_connection)
            if old['status']['state'] in ACTIVE_STATES:
                raise CallError('VM name can only be changed when VM is inactive')

            if old['name'] not in self.vms:
                raise CallError(f'Unable to locate domain for {old["name"]}')

        verrors = ValidationErrors()
        await self.common_validation(verrors, 'vm_update', new, old=old)
        verrors.check()

        for key in ('devices', 'status', 'display_available'):
            new.pop(key, None)

        await self.middleware.call('datastore.update', 'vm.vm', id_, new)

        vm_data = await self.get_instance(id_)
        if new['name'] != old['name']:
            await self.middleware.run_in_thread(self._rename_domain, old, vm_data)

        if old['shutdown_timeout'] != new['shutdown_timeout']:
            await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(id_)

    @accepts(
        Int('id'),
        Dict(
            'vm_delete',
            Bool('zvols', default=False),
            Bool('force', default=False),
        ),
    )
    async def do_delete(self, id_, data):
        """
        Delete a VM.
        """
        async with LIBVIRT_LOCK:
            vm = await self.get_instance(id_)
            # Deletion should be allowed even if host does not support virtualization
            if self._is_kvm_supported():
                await self.middleware.run_in_thread(self._check_setup_connection)
            status = await self.middleware.call('vm.status', id_)
            force_delete = data.get('force')
            if status['state'] in ACTIVE_STATES:
                await self.middleware.call('vm.poweroff', id_)
                # We would like to wait at least 7 seconds to have the vm
                # complete it's post vm actions which might require interaction with it's domain
                await asyncio.sleep(7)
            elif status.get('state') == 'ERROR' and not force_delete:
                raise CallError('Unable to retrieve VM status. Failed to destroy VM')

            if data['zvols']:
                devices = await self.middleware.call('vm.device.query', [
                    ('vm', '=', id_), ('dtype', '=', 'DISK')
                ])

                for zvol in devices:
                    if not zvol['attributes']['path'].startswith('/dev/zvol/'):
                        continue

                    disk_name = zvol_path_to_name(zvol['attributes']['path'])
                    try:
                        await self.middleware.call('zfs.dataset.delete', disk_name, {'recursive': True})
                    except Exception:
                        if not force_delete:
                            raise
                        else:
                            self.logger.error(
                                'Failed to delete %r volume when removing %r VM', disk_name, vm['name'], exc_info=True
                            )

            try:
                await self.middleware.run_in_thread(self._undefine_domain, vm['name'])
            except Exception:
                if not force_delete:
                    raise
                else:
                    self.logger.error(
                        'Failed to un-define %r VM\'s domain', vm['name'], exc_info=True)

            # We remove vm devices first
            for device in vm['devices']:
                await self.middleware.call('vm.device.delete', device['id'], {'force': data['force']})
            result = await self.middleware.call('datastore.delete', 'vm.vm', id_)
            if not await self.middleware.call('vm.query'):
                await self.middleware.call('vm.deinitialize_vms')
                self._clear()
            else:
                await self.middleware.call('etc.generate', 'libvirt_guests')
            return result

    @item_method
    @accepts(Int('id'), roles=['VM_READ'])
    @returns(Dict(
        'vm_status',
        Str('state', required=True),
        Int('pid', null=True, required=True),
        Str('domain_state', required=True),
    ))
    def status(self, id_):
        """
        Get the status of `id` VM.

        Returns a dict:
            - state, RUNNING / STOPPED / SUSPENDED
            - pid, process id if RUNNING
        """
        vm = self.middleware.call_sync('datastore.query', 'vm.vm', [['id', '=', id_]], {'get': True})
        self._check_setup_connection()
        return self.status_impl(vm)

    @private
    def status_impl(self, vm):
        if self._has_domain(vm['name']):
            try:
                # Whatever happens, query shouldn't fail
                return self._status(vm['name'])
            except Exception:
                self.logger.debug('Failed to retrieve VM status for %r', vm['name'], exc_info=True)

        return {
            'state': 'ERROR',
            'pid': None,
            'domain_state': 'ERROR',
        }

    @accepts(Int('id'), roles=['VM_READ'])
    @returns(Str(null=True))
    def log_file_path(self, vm_id):
        """
        Retrieve log file path of `id` VM.

        It will return path of the log file if it exists and `null` otherwise.
        """
        vm = self.middleware.call_sync('vm.get_instance', vm_id)
        path = f'/var/log/libvirt/qemu/{vm["id"]}_{vm["name"]}.log'
        return path if os.path.exists(path) else None
