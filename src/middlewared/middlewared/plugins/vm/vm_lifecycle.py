from middlewared.schema import accepts, Bool, Dict, Int, returns
from middlewared.service import CallError, item_method, job, Service
from middlewared.utils import osc

from .vm_supervisor import VMSupervisorMixin


class VMService(Service, VMSupervisorMixin):

    @item_method
    @accepts(Int('id'), Dict('options', Bool('overcommit', default=False)))
    @returns()
    async def start(self, id, options):
        """
        Start a VM.

        options.overcommit defaults to false, meaning VMs are not allowed to
        start if there is not enough available memory to hold all configured VMs.
        If true, VM starts even if there is not enough memory for all configured VMs.

        Error codes:

            ENOMEM(12): not enough free memory to run the VM without overcommit
        """
        await self.middleware.run_in_thread(self._check_setup_connection)

        vm = await self.middleware.call('vm.get_instance', id)
        if vm['status']['state'] == 'RUNNING':
            raise CallError(f'{vm["name"]} is already running')

        if osc.IS_FREEBSD and not await self.middleware.call('vm.validate_slots', vm):
            raise CallError(
                'Please adjust the devices attached to this VM. '
                f'A maximum of {await self.middleware.call("vm.available_slots")} PCI slots are allowed.'
            )

        if not await self.middleware.call('vm.supports_virtualization'):
            raise CallError('This system does not support virtualization.')

        if osc.IS_LINUX and vm['bootloader'] not in await self.middleware.call('vm.bootloader_options'):
            raise CallError(f'"{vm["bootloader"]}" is not supported on this platform.')

        # Perhaps we should have a default config option for VMs?
        await self.middleware.call('vm.init_guest_vmemory', vm, options['overcommit'])

        try:
            await self.middleware.run_in_thread(self._start, vm['name'])
        except Exception:
            if (await self.middleware.call('vm.get_instance', id))['status']['state'] != 'RUNNING':
                await self.middleware.call('vm.teardown_guest_vmemory', id)
            raise

    @item_method
    @accepts(
        Int('id'),
        Dict(
            'options',
            Bool('force', default=False),
            Bool('force_after_timeout', default=False),
        ),
    )
    @returns()
    @job(lock=lambda args: f'stop_vm_{args[0]}_{args[1].get("force") if len(args) == 2 else False}')
    def stop(self, job, id, options):
        """
        Stops a VM.

        For unresponsive guests who have exceeded the `shutdown_timeout` defined by the user and have become
        unresponsive, they required to be powered down using `vm.poweroff`. `vm.stop` is only going to send a
        shutdown signal to the guest and wait the desired `shutdown_timeout` value before tearing down guest vmemory.

        `force_after_timeout` when supplied, it will initiate poweroff for the VM forcing it to exit if it has
        not already stopped within the specified `shutdown_timeout`.
        """
        self._check_setup_connection()
        vm_data = self.middleware.call_sync('vm.get_instance', id)

        if options['force']:
            self._poweroff(vm_data['name'])
        else:
            self._stop(vm_data['name'], vm_data['shutdown_timeout'])

        if options['force_after_timeout'] and self.middleware.call_sync('vm.status', id)['state'] == 'RUNNING':
            self._poweroff(vm_data['name'])

        self.middleware.call_sync('vm.teardown_guest_vmemory', id)

    @item_method
    @accepts(Int('id'))
    @returns()
    def poweroff(self, id):
        """
        Poweroff a VM.
        """
        self._check_setup_connection()

        vm_data = self.middleware.call_sync('vm.get_instance', id)
        self._poweroff(vm_data['name'])
        self.middleware.call_sync('vm.teardown_guest_vmemory', id)

    @item_method
    @accepts(Int('id'))
    @returns()
    @job(lock=lambda args: f'restart_vm_{args[0]}')
    def restart(self, job, id):
        """
        Restart a VM.
        """
        self._check_setup_connection()
        vm = self.middleware.call_sync('vm.get_instance', id)
        self._restart(vm['name'])
