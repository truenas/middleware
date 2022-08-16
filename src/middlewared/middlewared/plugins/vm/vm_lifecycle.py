import asyncio

from middlewared.schema import accepts, Bool, Dict, Int, returns
from middlewared.service import CallError, item_method, job, private, Service

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
        vm_state = vm['status']['state']
        if vm_state == 'RUNNING':
            raise CallError(f'{vm["name"]!r} is already running')
        if vm_state == 'PAUSED':
            raise CallError(f'{vm["name"]!r} VM is paused and can only be resumed/powered off')

        if vm['bootloader'] not in await self.middleware.call('vm.bootloader_options'):
            raise CallError(f'"{vm["bootloader"]}" is not supported on this platform.')

        # Perhaps we should have a default config option for VMs?
        await self.middleware.call('vm.init_guest_vmemory', vm, options['overcommit'])

        try:
            await self.middleware.run_in_thread(self._start, vm['name'])
        except Exception:
            if (await self.middleware.call('vm.get_instance', id))['status']['state'] != 'RUNNING':
                await self.middleware.call('vm.teardown_guest_vmemory', id)
            raise

        await self.middleware.call('service.reload', 'haproxy')

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
        stop_job = self.middleware.call_sync('vm.stop', id, {'force_after_timeout': True})
        stop_job.wait_sync()
        if stop_job.error:
            raise CallError(f'Failed to stop {vm["name"]!r} vm: {stop_job.error}')

        self.start(id, {'overcommit': True})

    @item_method
    @accepts(Int('id'))
    @returns()
    def suspend(self, id):
        """
        Suspend `id` VM.
        """
        self._check_setup_connection()

        vm = self.middleware.call_sync('vm.get_instance', id)
        self._suspend(vm['name'])

    @item_method
    @accepts(Int('id'))
    @returns()
    def resume(self, id):
        """
        Resume suspended `id` VM.
        """
        self._check_setup_connection()

        vm = self.middleware.call_sync('vm.get_instance', id)
        self._resume(vm['name'])

    @private
    def suspend_vms(self, vm_ids):
        for vm in vm_ids:
            try:
                self.suspend(vm['id'])
            except Exception:
                self.logger.error('Failed to suspend %r vm', vm['name'], exc_info=True)

    @private
    def resume_suspended_vms(self, vm_ids):
        for vm in vm_ids:
            try:
                self.resume(vm['id'])
            except Exception:
                self.logger.error('Failed to resume %r vm', vm['name'], exc_info=True)


async def _event_vms(middleware, event_type, args):
    vm = await middleware.call('vm.query', [['id', '=', args['id']]])
    if not vm or vm[0]['status']['state'] != 'STOPPED' or args.get('state') != 'SHUTOFF':
        return

    asyncio.ensure_future(middleware.call('vm.teardown_guest_vmemory', args['id']))
    await middleware.call('service.reload', 'haproxy')


async def setup(middleware):
    middleware.event_subscribe('vm.query', _event_vms)
