import errno

from middlewared.api import api_method
from middlewared.api.current import (
    VirtInstanceGetAvailableMemoryArgs, VirtInstanceGetAvailableMemoryResult, VirtInstanceGetVMMemoryInfoArgs,
    VirtInstanceGetVMMemoryInfoResult,
)
from middlewared.service import CallError, Service
from middlewared.utils.memory import get_memory_info

from .utils import get_max_requested_memory_of_instance


class VirtInstanceService(Service):

    class Config:
        namespace = 'virt.instance'
        cli_namespace = 'virt.instance'

    @api_method(VirtInstanceGetAvailableMemoryArgs, VirtInstanceGetAvailableMemoryResult, roles=['VIRT_INSTANCE_READ'])
    async def get_available_memory(self, overcommit):
        """
        Get the current maximum amount of available memory to be allocated for VMs.

        In case of `overcommit` being `true`, calculations are done in the following manner:
        1. If a VM has requested 10G but is only consuming 5G, only 5G will be counted
        2. System will consider shrinkable ZFS ARC as free memory ( shrinkable ZFS ARC is current ZFS ARC
           minus ZFS ARC minimum )

        In case of `overcommit` being `false`, calculations are done in the following manner:
        1. Complete VM requested memory will be taken into account regardless of how much actual physical
           memory the VM is consuming
        2. System will not consider shrinkable ZFS ARC as free memory

        Memory is of course a very "volatile" resource, values may change abruptly between a
        second but I deem it good enough to give the user a clue about how much memory is
        available at the current moment and if a VM should be allowed to be launched.
        """
        # Use 90% of available memory to play safe
        free = int(get_memory_info()['available'] * 0.9)

        # Difference between current ARC total size and the minimum allowed
        arc_total = await self.middleware.call('sysctl.get_arcstats_size')
        arc_min = await self.middleware.call('sysctl.get_arc_min')
        arc_shrink = max(0, arc_total - arc_min)
        total_free = free + arc_shrink

        vms_memory_used = 0
        if overcommit is False:
            # If overcommit is not wanted its verified how much physical memory
            # the vm process is currently using and add the maximum memory its
            # supposed to have.
            for vm in await self.middleware.call(
                'virt.instance.query', [['type', '=', 'VM'], ['status', '=', 'RUNNING']], {
                    'extra': {'raw': True},
                }
            ):
                if (memory_info := vm['raw'].get('state', {}).get('memory', {})) and memory_info.get('usage'):
                    current_vm_mem = memory_info['usage']
                    vm_max_mem = vm['memory'] if vm['memory'] else (memory_info['total'] or current_vm_mem)
                else:
                    continue

                # We handle edge case with vm_max_mem < current_vm_mem
                if vm_max_mem > current_vm_mem:
                    vms_memory_used += vm_max_mem - current_vm_mem

        return max(0, total_free - vms_memory_used)

    @api_method(VirtInstanceGetVMMemoryInfoArgs, VirtInstanceGetVMMemoryInfoResult, roles=['VIRT_INSTANCE_READ'])
    async def get_vm_memory_info(self, vm_id):
        """
        Returns memory information for `vm_id` virt VM if it is going to be started.

        All memory attributes are expressed in bytes.
        """
        vm = await self.middleware.call('virt.instance.get_instance', vm_id, {'extra': {'raw': True}})
        if vm['type'] != 'VM':
            raise CallError(f'Virt instance is not a VM: {vm["name"]}', errno.EINVAL)

        arc_max = await self.middleware.call('sysctl.get_arc_max')
        arc_min = await self.middleware.call('sysctl.get_arc_min')
        shrinkable_arc_max = max(0, arc_max - arc_min)

        available_memory = await self.get_available_memory(False)
        available_memory_with_overcommit = await self.get_available_memory(True)
        vm_requested_memory = get_max_requested_memory_of_instance(vm)

        overcommit_required = vm_requested_memory > available_memory
        arc_to_shrink = 0
        if overcommit_required:
            arc_to_shrink = min(shrinkable_arc_max, vm_requested_memory - available_memory)

        return {
            'total_memory_requested': vm_requested_memory,
            'overcommit_required': overcommit_required,
            'arc_to_shrink': arc_to_shrink,
            'memory_req_fulfilled_after_overcommit': vm_requested_memory < available_memory_with_overcommit,
            'current_arc_max': arc_max,
            'arc_min': arc_min,
            'arc_max_after_shrink': arc_max - arc_to_shrink,
            'actual_vm_requested_memory': vm_requested_memory,
        }
