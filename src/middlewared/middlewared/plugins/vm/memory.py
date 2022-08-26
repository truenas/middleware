import errno

from middlewared.schema import accepts, Int, returns
from middlewared.service import CallError, private, Service

from .utils import ACTIVE_STATES
from .vm_supervisor import VMSupervisorMixin


class VMService(Service, VMSupervisorMixin):

    async def _set_guest_vmemory(self, vm_id, overcommit):
        vm = await self.middleware.call('vm.get_instance', vm_id)
        memory_details = await self.middleware.call('vm.get_vm_memory_info', vm_id)
        if not memory_details['overcommit_required']:
            # There really isn't anything to be done if over-committing is not required
            return

        if not overcommit:
            raise CallError(f'Cannot guarantee memory for guest {vm["name"]}', errno.ENOMEM)

        if memory_details['current_arc_max'] != memory_details['arc_max_after_shrink']:
            self.logger.debug(
                'Setting ARC from %s to %s', memory_details['current_arc_max'], memory_details['arc_max_after_shrink']
            )
            await self.middleware.call('sysctl.set_arc_max', memory_details['arc_max_after_shrink'])

    @private
    async def init_guest_vmemory(self, vm, overcommit):
        guest_status = await self.middleware.call('vm.status', vm['id'])
        if guest_status.get('state') not in ACTIVE_STATES:
            await self._set_guest_vmemory(vm['id'], overcommit)
        else:
            raise CallError('VM process is running, we won\'t allocate memory')

    @private
    async def teardown_guest_vmemory(self, vm_id):
        vm = await self.middleware.call('vm.get_instance', vm_id)
        if vm['status']['state'] != 'STOPPED':
            return

        guest_memory = vm['memory'] * 1024 * 1024
        arc_max = await self.middleware.call('sysctl.get_arc_max')
        arc_min = await self.middleware.call('sysctl.get_arc_min')
        new_arc_max = min(
            await self.middleware.call('sysctl.get_default_arc_max'),
            arc_max + guest_memory
        )
        if arc_max != new_arc_max:
            if new_arc_max > arc_min:
                self.logger.debug(f'Giving back guest memory to ARC: {new_arc_max}')
                await self.middleware.call('sysctl.set_arc_max', new_arc_max)
            else:
                self.logger.warn(
                    f'Not giving back memory to ARC because new arc_max ({new_arc_max}) <= arc_min ({arc_min})'
                )

    @accepts(Int('vm_id'))
    @returns(Int('memory_usage', description='Memory usage of a VM in bytes'))
    def get_memory_usage(self, vm_id):
        return self.get_memory_usage_internal(self.middleware.call_sync('vm.get_instance', vm_id))

    @private
    def get_memory_usage_internal(self, vm):
        return self._memory_info(vm['name'])
