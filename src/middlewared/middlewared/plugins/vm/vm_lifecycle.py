from truenas_pylibvirt import (
    NICDevice, NICDeviceType,
    DiskStorageDevice, StorageDeviceType, StorageDeviceIoType,
    VmBootloader, VmCpuMode, VmDomain, VmDomainConfiguration,
)

from middlewared.api import api_method
from middlewared.api.current import (
    VMStartArgs, VMStartResult, VMStopArgs, VMStopResult, VMRestartArgs, VMRestartResult, VMPoweroffArgs,
    VMPoweroffResult, VMSuspendArgs, VMSuspendResult, VMResumeArgs, VMResumeResult,
)
from middlewared.service import CallError, item_method, job, private, Service

from .vm_supervisor import VMSupervisorMixin


class VMService(Service, VMSupervisorMixin):
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

        self.middleware.libvirt_domains_manager.vms.start(self.pylibvirt_vm(vm))

        return

        # FIXME: Move this code to pylibvirt
        """
        vm_state = vm['status']['state']
        if vm_state == 'RUNNING':
            raise CallError(f'{vm["name"]!r} is already running')
        if vm_state == 'SUSPENDED':
            raise CallError(f'{vm["name"]!r} VM is suspended and can only be resumed/powered off')

        if vm['bootloader'] not in await self.middleware.call('vm.bootloader_options'):
            raise CallError(f'"{vm["bootloader"]}" is not supported on this platform.')

        if await self.middleware.call('system.is_ha_capable'):
            for device in vm['devices']:
                if device['attributes']['dtype'] in ('PCI', 'USB'):
                    raise CallError(
                        'Please remove PCI/USB devices from VM before starting it in HA capable machines as '
                        'they are not supported.'
                    )

        # Perhaps we should have a default config option for VMs?
        await self.middleware.call('vm.init_guest_vmemory', vm, options['overcommit'])

        try:
            await self.middleware.run_in_thread(self._start, vm['name'])
        except Exception:
            if (await self.middleware.call('vm.get_instance', id_))['status']['state'] != 'RUNNING':
                await self.middleware.call('vm.teardown_guest_vmemory', id_)
            raise

        await (await self.middleware.call('service.control', 'RELOAD', 'http')).wait(raise_error=True)
        """

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
        self._check_setup_connection()
        vm_data = self.middleware.call_sync('vm.get_instance', id_)

        if options['force']:
            self._poweroff(vm_data['name'])
        else:
            self._stop(vm_data['name'], vm_data['shutdown_timeout'])

        if options['force_after_timeout'] and self.middleware.call_sync('vm.status', id_)['state'] == 'RUNNING':
            self._poweroff(vm_data['name'])

    @item_method
    @api_method(VMPoweroffArgs, VMPoweroffResult, roles=['VM_WRITE'])
    def poweroff(self, id_):
        """
        Poweroff a VM.
        """
        self._check_setup_connection()

        vm_data = self.middleware.call_sync('vm.get_instance', id_)
        self._poweroff(vm_data['name'])

    @item_method
    @api_method(VMRestartArgs, VMRestartResult, roles=['VM_WRITE'])
    @job(lock=lambda args: f'restart_vm_{args[0]}')
    def restart(self, job, id_):
        """
        Restart a VM.
        """
        self._check_setup_connection()
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
        self._check_setup_connection()

        vm = self.middleware.call_sync('vm.get_instance', id_)
        self._suspend(vm['name'])

    @item_method
    @api_method(VMResumeArgs, VMResumeResult, roles=['VM_WRITE'])
    def resume(self, id_):
        """
        Resume suspended `id` VM.
        """
        self._check_setup_connection()

        vm = self.middleware.call_sync('vm.get_instance', id_)
        self._resume(vm['name'])

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
    def pylibvirt_vm(self, vm):
        vm = vm.copy()
        vm.pop("id", None)
        vm.pop("display_available", None)
        vm.pop("status", None)

        vm["bootloader"] = VmBootloader(vm["bootloader"])
        vm["cpu_mode"] = VmCpuMode(vm["cpu_mode"])

        devices = []
        for device in vm["devices"]:
            match device["attributes"]["dtype"]:
                case "DISK":
                    devices.append(DiskStorageDevice(
                        type_=StorageDeviceType(device["attributes"]["type"]),
                        logical_sectorsize=device["attributes"]["logical_sectorsize"],
                        physical_sectorsize=device["attributes"]["physical_sectorsize"],
                        iotype=StorageDeviceIoType(device["attributes"]["iotype"]),
                        serial=device["attributes"]["serial"],
                        path=device["attributes"]["path"],
                    ))

                case "NIC":
                    if device["attributes"]["nic_attach"].startswith("br"):
                        type_ = NICDeviceType.BRIDGE
                    else:
                        type_ = NICDeviceType.DIRECT

                    devices.append(NICDevice(
                        type_=type_,
                        source=device["attributes"]["nic_attach"],
                        model=None,
                        mac=None,
                        trust_guest_rx_filters=device["attributes"]["trust_guest_rx_filters"],
                    ))

        vm["devices"] = devices

        return VmDomain(VmDomainConfiguration(**vm))


async def _event_vms(middleware, event_type, args):
    vm = await middleware.call('vm.query', [['id', '=', args['id']]])
    if not vm or vm[0]['status']['state'] != 'STOPPED' or args.get('state') != 'SHUTOFF':
        return

    middleware.create_task(middleware.call('vm.teardown_guest_vmemory', args['id']))


async def setup(middleware):
    middleware.event_subscribe('vm.query', _event_vms)
