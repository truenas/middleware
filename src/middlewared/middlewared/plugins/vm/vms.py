import asyncio
import errno
import functools
import os
import re
import shlex
import shutil
import uuid

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    VMEntry, VMCreateArgs, VMCreateResult, VMUpdateArgs, VMUpdateResult, VMDeleteArgs, VMDeleteResult,
    VMBootloaderOvmfChoicesArgs, VMBootloaderOvmfChoicesResult, VMBootloaderOptionsArgs, VMBootloaderOptionsResult,
    VMStatusArgs, VMStatusResult, VMLogFilePathArgs, VMLogFilePathResult, VMLogFileDownloadArgs,
    VMLogFileDownloadResult,
)
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.service import CallError, CRUDService, item_method, job, private, ValidationErrors
from middlewared.plugins.vm.numeric_set import parse_numeric_set

from .utils import ACTIVE_STATES, get_default_status, get_vm_nvram_file_name, SYSTEM_NVRAM_FOLDER_PATH
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
    enable_cpu_topology_extension = sa.Column(sa.Boolean(), default=False)
    enable_secure_boot = sa.Column(sa.Boolean(), default=False, nullable=False)


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
        entry = VMEntry

    @api_method(VMBootloaderOvmfChoicesArgs, VMBootloaderOvmfChoicesResult, roles=['VM_READ'])
    def bootloader_ovmf_choices(self):
        """
        Retrieve bootloader ovmf choices
        """
        return {path: path for path in ovmf_options()}

    @private
    def extend_context(self, rows, extra):
        status = {}
        shutting_down = self.middleware.call_sync('system.state') == 'SHUTTING_DOWN'
        kvm_supported = self._is_kvm_supported()
        if shutting_down is False and rows and kvm_supported:
            self._safely_check_setup_connection(5)

        libvirt_running = shutting_down is False and self._is_connection_alive()
        for row in rows:
            status[row['id']] = self.status_impl(row) if libvirt_running else get_default_status()

        return {
            'status': status,
        }

    @api_method(VMBootloaderOptionsArgs, VMBootloaderOptionsResult, roles=['VM_READ'])
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
        vm['display_available'] = any(device['attributes']['dtype'] == 'DISPLAY' for device in vm['devices'])
        vm['status'] = context['status'][vm['id']]
        return vm

    @api_method(VMCreateArgs, VMCreateResult)
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
        """
        async with LIBVIRT_LOCK:
            await self.middleware.run_in_thread(self._check_setup_connection)

        verrors = ValidationErrors()
        await self.common_validation(verrors, 'vm_create', data)

        if data['bootloader_ovmf'] and data['bootloader_ovmf'] not in await self.middleware.call(
            'vm.bootloader_ovmf_choices'
        ):
            verrors.add(
                'vm_create.bootloader_ovmf',
                'Invalid bootloader ovmf choice specified'
            )

        if data['enable_secure_boot']:
            # Only q35 machine type supports secure boot
            # https://docs.openstack.org/nova/latest/admin/secure-boot.html
            if not data['machine_type']:
                data['machine_type'] = 'pc-q35-6.2'
                if not data['arch_type']:
                    # If arch type is not specified, we assume x86_64 architecture
                    # we set this because otherwise vm.update will fail if this is not set
                    # explicitly
                    data['arch_type'] = 'x86_64'
            elif data['machine_type'] and 'pc-q35' not in data['machine_type']:
                verrors.add(
                    'vm_create.machine_type',
                    'Secure boot is only available in q35 machine type'
                )

            if data['bootloader_ovmf'] is None:
                data['bootloader_ovmf'] = 'OVMF_CODE_4M.secboot.fd'

            if 'secboot' not in data['bootloader_ovmf'].lower():
                verrors.add(
                    'vm_create.bootloader_ovmf',
                    'Select a bootloader_ovmf that supports secure boot i.e OVMF_CODE_4M.secboot.fd'
                )

        if data['bootloader_ovmf'] is None:
            data['bootloader_ovmf'] = 'OVMF_CODE_4M.fd'

        verrors.check()

        vm_id = await self.middleware.call('datastore.insert', 'vm.vm', data)
        await self.middleware.run_in_thread(self._add, vm_id)
        await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(vm_id)

    @private
    async def common_validation(self, verrors, schema_name, data, old=None):
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
                    f'"{schema_name}.threads" is less than {max_vcpus}.'
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
                    f'Number of cpus in "{schema_name}.cpuset" must be equal to total number '
                    'vcpus if pinning is enabled.'
                )

        # TODO: Let's please implement PCI express hierarchy as the limit on devices in KVM is quite high
        # with reports of users having thousands of disks
        # Let's validate that the VM has the correct no of slots available to accommodate currently configured devices

    @api_method(VMUpdateArgs, VMUpdateResult)
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
            try:
                new_path = os.path.join(SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name(new))
                await self.middleware.run_in_thread(
                    os.rename, os.path.join(SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name(old)), new_path
                )
            except FileNotFoundError:
                if old['bootloader'] == new['bootloader'] == 'UEFI':
                    # So we only want to raise an error if bootloader is UEFI because for BIOS
                    # nvram file will not exist and it is fine. If bootloader is changed from
                    # BIOS to UEFI, even then we will not have it and it is fine so we don't want
                    # to raise an error in that case.
                    raise CallError(
                        f'VM name has been updated but nvram file for {old["name"]} does not exist '
                        f'which can result in {new["name"]} VM not booting properly.'
                    )

        if old['shutdown_timeout'] != new['shutdown_timeout']:
            await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(id_)

    @api_method(VMDeleteArgs, VMDeleteResult)
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
            else:
                status = vm['status']

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
                    ('vm', '=', id_), ('attributes.dtype', '=', 'DISK')
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
                    self.logger.error("Failed to un-define %r VM's domain", vm['name'], exc_info=True)

            # We remove vm devices first
            for device in vm['devices']:
                await self.middleware.call('vm.device.delete', device['id'], {'force': data['force']})
            result = await self.middleware.call('datastore.delete', 'vm.vm', id_)
            if not await self.middleware.call('vm.query'):
                await self.middleware.call('vm.deinitialize_vms', {'reload_ui': False})
                self._clear()
            else:
                await self.middleware.call('etc.generate', 'libvirt_guests')
            return result

    @item_method
    @api_method(VMStatusArgs, VMStatusResult, roles=['VM_READ'])
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

        return get_default_status()

    @api_method(VMLogFilePathArgs, VMLogFilePathResult, roles=['VM_READ'])
    def log_file_path(self, vm_id):
        """
        Retrieve log file path of `id` VM.

        It will return path of the log file if it exists and `null` otherwise.
        """
        vm = self.middleware.call_sync('vm.get_instance', vm_id)
        path = f'/var/log/libvirt/qemu/{vm["id"]}_{vm["name"]}.log'
        return path if os.path.exists(path) else None

    @api_method(VMLogFileDownloadArgs, VMLogFileDownloadResult, roles=['VM_READ'])
    @job(pipes=['output'])
    def log_file_download(self, job, vm_id):
        """
        Retrieve log file contents of `id` VM.

        It will download empty file if log file does not exist.
        """
        if path := self.log_file_path(vm_id):
            with open(path, 'rb') as f:
                shutil.copyfileobj(f, job.pipes.output.w)
