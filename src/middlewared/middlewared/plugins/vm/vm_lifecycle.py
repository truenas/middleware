import os

from truenas_pylibvirt import VmBootloader, VmCpuMode

from middlewared.api import api_method
from middlewared.api.current import (
    VMStartArgs, VMStartResult, VMStopArgs, VMStopResult, VMRestartArgs, VMRestartResult, VMPoweroffArgs,
    VMPoweroffResult, VMSuspendArgs, VMSuspendResult, VMResumeArgs, VMResumeResult,
)
from middlewared.service import CallError, item_method, job, private, Service
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .vm_domain import VmDomain, VmDomainConfiguration
from .utils import get_vm_tpm_state_dir_name, get_vm_nvram_file_name, SYSTEM_TPM_FOLDER_PATH, SYSTEM_NVRAM_FOLDER_PATH


class VMService(Service):

    @private
    async def lifecycle_action_check(self):
        if not await self.middleware.call('vm.license_active'):
            raise CallError('Requested action cannot be performed as system is not licensed to use VMs')

    @item_method
    @api_method(VMStartArgs, VMStartResult, roles=['VM_WRITE'])
    def start(self, id_, options):
        """
        Start a VM.

        options.overcommit defaults to false, meaning VMs are not allowed to
        start if there is not enough available memory to hold all configured VMs.
        If true, VM starts even if there is not enough memory for all configured VMs.

        Error codes:

            ENOMEM(12): not enough free memory to run the VM without overcommit
        """
        self.middleware.call_sync('vm.lifecycle_action_check')

        vm = self.middleware.call_sync('vm.get_instance', id_)
        if vm['status']['state'] in ACTIVE_STATES:
            raise CallError(f'VM {vm["name"]!r} is already running')

        if vm['bootloader'] not in self.middleware.call_sync('vm.bootloader_options'):
            raise CallError(f'"{vm["bootloader"]}" is not supported on this platform.')

        # Check HA compatibility
        if self.middleware.call_sync('system.is_ha_capable'):
            for device in vm['devices']:
                if device['attributes']['dtype'] in ('PCI', 'USB'):
                    raise CallError(
                        'Please remove PCI/USB devices from VM before starting it in HA capable machines'
                    )

        # Start the VM using pylibvirt
        self.middleware.libvirt_domains_manager.vms.start(self.pylibvirt_vm(vm, options))

        # Reload HTTP service for display device changes
        self.middleware.call_sync('service.control', 'RELOAD', 'http').wait_sync(raise_error=True)

    @item_method
    @api_method(VMStopArgs, VMStopResult, roles=['VM_WRITE'])
    @job(lock=lambda args: f'stop_vm_{args[0]}')
    def stop(self, job, id_, options):
        """
        Stops a VM.

        For unresponsive guests who have exceeded the `shutdown_timeout` defined by the user and have become
        unresponsive, they required to be powered down using `vm.poweroff`. `vm.stop` is only going to send a
        shutdown signal to the guest and wait the desired `shutdown_timeout` value before tearing down guest vmemory.

        `force_after_timeout` when supplied, it will initiate poweroff for the VM forcing it to exit if it has
        not already stopped within the specified `shutdown_timeout`.
        """
        vm_data = self.middleware.call_sync('vm.get_instance', id_)
        libvirt_domain = self.pylibvirt_vm(vm_data)
        if options['force']:
            self.middleware.libvirt_domains_manager.vms.destroy(libvirt_domain)
        else:
            self.middleware.libvirt_domains_manager.vms.shutdown(libvirt_domain, vm_data['shutdown_timeout'])

    @item_method
    @api_method(VMPoweroffArgs, VMPoweroffResult, roles=['VM_WRITE'])
    def poweroff(self, id_):
        """
        Poweroff a VM.
        """
        vm_data = self.middleware.call_sync('vm.get_instance', id_)
        self.middleware.libvirt_domains_manager.vms.destroy(self.pylibvirt_vm(vm_data))

    @item_method
    @api_method(VMRestartArgs, VMRestartResult, roles=['VM_WRITE'])
    @job(lock=lambda args: f'restart_vm_{args[0]}')
    def restart(self, job, id_):
        """
        Restart a VM.
        """
        vm = self.middleware.call_sync('vm.get_instance', id_)
        stop_job = self.middleware.call_sync('vm.stop', id_, {'force_after_timeout': True})
        stop_job.wait_sync()
        if stop_job.error:
            raise CallError(f'Failed to stop {vm["name"]!r} vm: {stop_job.error}')

        self.middleware.call_sync('vm.start', id_, {'overcommit': True})

    @item_method
    @api_method(VMSuspendArgs, VMSuspendResult, roles=['VM_WRITE'])
    def suspend(self, id_):
        """
        Suspend `id` VM.
        """
        vm_data = self.middleware.call_sync('vm.get_instance', id_)
        self.middleware.libvirt_domains_manager.vms.suspend(self.pylibvirt_vm(vm_data))

    @item_method
    @api_method(VMResumeArgs, VMResumeResult, roles=['VM_WRITE'])
    def resume(self, id_):
        """
        Resume suspended `id` VM.
        """
        vm_data = self.middleware.call_sync('vm.get_instance', id_)
        self.middleware.libvirt_domains_manager.vms.resume(self.pylibvirt_vm(vm_data))

    @private
    def suspend_vms(self, vm_ids):
        vms = {vm['id']: vm for vm in self.middleware.call_sync('vm.query')}
        for vm_id in filter(
            lambda vm_id: vms.get(vm_id).get('status', {}).get('state') == 'RUNNING',
            map(int, vm_ids)
        ):
            try:
                self.suspend(vm_id)
            except Exception:
                self.logger.error('Failed to suspend %r vm', vms[vm_id]['name'], exc_info=True)

    @private
    def resume_suspended_vms(self, vm_ids):
        vms = {vm['id']: vm for vm in self.middleware.call_sync('vm.query')}
        for vm_id in filter(
            lambda vm_id: vms.get(vm_id).get('status', {}).get('state') == 'SUSPENDED',
            map(int, vm_ids)
        ):
            try:
                self.resume(vm_id)
            except Exception:
                self.logger.error('Failed to resume %r vm', vms[vm_id]['name'], exc_info=True)

    @private
    def pylibvirt_vm(self, vm, start_config: dict | None = None) -> VmDomain:
        vm = vm.copy()
        vm.pop("display_available", None)
        vm.pop("status", None)

        devices = []
        for device in vm["devices"]:
            devices.append(self.middleware.call_sync('vm.device.get_pylibvirt_device', device))

        vm.update({
            'bootloader': VmBootloader(vm["bootloader"]),
            'cpu_mode': VmCpuMode(vm["cpu_mode"]),
            'nvram_path': os.path.join(SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name({
                'id': vm['id'],
                'name': vm['name'],
            })),
            'tpm_path': os.path.join(SYSTEM_TPM_FOLDER_PATH, get_vm_tpm_state_dir_name(vm)),
            'devices': devices,
        })

        return VmDomain(VmDomainConfiguration(**vm), self.middleware, start_config)
