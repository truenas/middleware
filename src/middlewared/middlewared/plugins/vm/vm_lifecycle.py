from middlewared.schema import accepts, Bool, Dict, Int, returns
from middlewared.service import CallError, item_method, job, private, Service

from .vm_supervisor import VMSupervisorMixin


class VMService(Service, VMSupervisorMixin):

    @private
    async def lifecycle_action_check(self):
        if not await self.middleware.call('vm.license_active'):
            raise CallError('Requested action cannot be performed as system is not licensed to use VMs')

    @item_method
    @accepts(
        Int('id'),
        Dict('options', Bool('overcommit', default=False)),
        roles=['VM_WRITE']
    )
    @returns()
    async def start(self, id_, options):
        """
        Start a VM.

        options.overcommit defaults to false, meaning VMs are not allowed to
        start if there is not enough available memory to hold all configured VMs.
        If true, VM starts even if there is not enough memory for all configured VMs.

        Error codes:

            ENOMEM(12): not enough free memory to run the VM without overcommit
        """
        await self.lifecycle_action_check()
        await self.middleware.run_in_thread(self._check_setup_connection)

        vm = await self.middleware.call('vm.get_instance', id_)
        vm_state = vm['status']['state']
        if vm_state == 'RUNNING':
            raise CallError(f'{vm["name"]!r} is already running')
        if vm_state == 'SUSPENDED':
            raise CallError(f'{vm["name"]!r} VM is suspended and can only be resumed/powered off')

        if vm['bootloader'] not in await self.middleware.call('vm.bootloader_options'):
            raise CallError(f'"{vm["bootloader"]}" is not supported on this platform.')

        if vm['bootloader'] == 'UEFI' and not vm['nvram_location']:
            raise CallError('UEFI VMs require a NVRAM file to be set before they can be started')

        if await self.middleware.call('system.is_ha_capable'):
            for device in vm['devices']:
                if device['dtype'] in ('PCI', 'USB'):
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

        await self.middleware.call('service.reload', 'http')

    @item_method
    @accepts(
        Int('id'),
        Dict(
            'options',
            Bool('force', default=False),
            Bool('force_after_timeout', default=False),
        ),
        roles=['VM_WRITE']
    )
    @returns()
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
    @accepts(Int('id'), roles=['VM_WRITE'])
    @returns()
    def poweroff(self, id_):
        """
        Poweroff a VM.
        """
        self._check_setup_connection()

        vm_data = self.middleware.call_sync('vm.get_instance', id_)
        self._poweroff(vm_data['name'])

    @item_method
    @accepts(Int('id'), roles=['VM_WRITE'])
    @returns()
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
    @accepts(Int('id'), roles=['VM_WRITE'])
    @returns()
    def suspend(self, id_):
        """
        Suspend `id` VM.
        """
        self._check_setup_connection()

        vm = self.middleware.call_sync('vm.get_instance', id_)
        self._suspend(vm['name'])

    @item_method
    @accepts(Int('id'), roles=['VM_WRITE'])
    @returns()
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


async def _event_vms(middleware, event_type, args):
    vm = await middleware.call('vm.query', [['id', '=', args['id']]])
    if not vm or vm[0]['status']['state'] != 'STOPPED' or args.get('state') != 'SHUTOFF':
        return

    middleware.create_task(middleware.call('vm.teardown_guest_vmemory', args['id']))


async def setup(middleware):
    middleware.event_subscribe('vm.query', _event_vms)
