import psutil

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import CallError, Service
from middlewared.validators import MACAddr

from .devices import NIC
from .utils import ACTIVE_STATES


class VMService(Service):

    @accepts()
    @returns(Dict(
        'vmemory_in_use',
        Int('RNP', required=True, description='Running but not provisioned'),
        Int('PRD', required=True, description='Provisioned but not running'),
        Int('RPRD', required=True, description='Running and provisioned'),
    ))
    async def get_vmemory_in_use(self):
        """
        The total amount of virtual memory in MB used by guests

            Returns a dict with the following information:
                RNP - Running but not provisioned
                PRD - Provisioned but not running
                RPRD - Running and provisioned
        """
        memory_allocation = {'RNP': 0, 'PRD': 0, 'RPRD': 0}
        guests = await self.middleware.call('datastore.query', 'vm.vm')
        for guest in guests:
            status = await self.middleware.call('vm.status', guest['id'])
            if status['state'] in ACTIVE_STATES:
                memory_allocation['RPRD' if guest['autostart'] else 'RNP'] += guest['memory'] * 1024 * 1024
            elif guest['autostart']:
                memory_allocation['PRD'] += guest['memory'] * 1024 * 1024

        return memory_allocation

    @accepts(Bool('overcommit', default=False))
    @returns(Int('available_memory'))
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
        free = int(psutil.virtual_memory().available * 0.9)

        # swap used space is accounted for used physical memory because
        # 1. processes (including VMs) can be swapped out
        # 2. we want to avoid using swap
        swap_used = psutil.swap_memory().used

        # Difference between current ARC total size and the minimum allowed
        arc_total = await self.middleware.call('sysctl.get_arcstats_size')
        arc_min = await self.middleware.call('sysctl.get_arc_min')
        arc_shrink = max(0, arc_total - arc_min)
        total_free = free + arc_shrink if overcommit else free

        vms_memory_used = 0
        if overcommit is False:
            # If overcommit is not wanted its verified how much physical memory
            # the vm process is currently using and add the maximum memory its
            # supposed to have.
            for vm in await self.middleware.call('vm.query', [['status.state', 'in', ACTIVE_STATES]]):
                try:
                    current_vm_mem = await self.middleware.call('vm.get_memory_usage_internal', vm)
                except Exception:
                    self.logger.error('Unable to retrieve %r vm memory usage', vm['name'], exc_info=True)
                    continue
                else:
                    vm_max_mem = vm['memory'] * 1024 * 1024
                    # We handle edge case with vm_max_mem < current_vm_mem
                    if vm_max_mem > current_vm_mem:
                        vms_memory_used += vm_max_mem - current_vm_mem

        return max(0, total_free - vms_memory_used - swap_used)

    @accepts(Int('vm_id'))
    @returns(Dict(
        Int('minimum_memory_requested', description='Minimum memory requested by the VM'),
        Int('total_memory_requested', description='Maximum / total memory requested by the VM'),
        Bool('overcommit_required', description='Overcommit of memory is required to start VM'),
        Bool(
            'memory_req_fulfilled_after_overcommit',
            description='Memory requirements of VM are fulfilled if over-committing memory is specified'
        ),
        Int('arc_to_shrink', description='Size of ARC to shrink in bytes', null=True),
        Int('current_arc_max', description='Current size of max ARC in bytes'),
        Int('arc_min', description='Minimum size of ARC in bytes'),
        Int('arc_max_after_shrink', description='Size of max ARC in bytes after shrinking'),
        Int(
            'actual_vm_requested_memory',
            description='VM memory in bytes to consider when making calculations for available/required memory.'
                        ' If VM ballooning is specified for the VM, the minimum VM memory specified by user will'
                        ' be taken into account otherwise total VM memory requested will be taken into account.'
        ),
    ))
    async def get_vm_memory_info(self, vm_id):
        """
        Returns memory information for `vm_id` VM if it is going to be started.

        All memory attributes are expressed in bytes.
        """
        vm = await self.middleware.call('vm.get_instance', vm_id)
        if vm['status']['state'] in ACTIVE_STATES:
            # TODO: Let's add this later as we have a use case in the UI - could be useful to
            #  show separate info of each VM in the UI moving on
            raise CallError(f'Unable to retrieve {vm["name"]!r} VM information as it is already running.')

        arc_max = await self.middleware.call('sysctl.get_arc_max')
        arc_min = await self.middleware.call('sysctl.get_arc_min')
        shrinkable_arc_max = max(0, arc_max - arc_min)

        available_memory = await self.get_available_memory(False)
        available_memory_with_overcommit = await self.get_available_memory(True)
        vm_max_memory = vm['memory'] * 1024 * 1024
        vm_min_memory = vm['min_memory'] * 1024 * 1024 if vm['min_memory'] else None
        vm_requested_memory = vm_min_memory or vm_max_memory

        overcommit_required = vm_requested_memory > available_memory
        arc_to_shrink = 0
        if overcommit_required:
            arc_to_shrink = min(shrinkable_arc_max, vm_requested_memory - available_memory)

        return {
            'minimum_memory_requested': vm_min_memory,
            'total_memory_requested': vm_max_memory,
            'overcommit_required': overcommit_required,
            'arc_to_shrink': arc_to_shrink,
            'memory_req_fulfilled_after_overcommit': vm_requested_memory < available_memory_with_overcommit,
            'current_arc_max': arc_max,
            'arc_min': arc_min,
            'arc_max_after_shrink': arc_max - arc_to_shrink,
            'actual_vm_requested_memory': vm_requested_memory,
        }

    @accepts()
    @returns(Str('mac', validators=[MACAddr(separator=':')]),)
    def random_mac(self):
        """
        Create a random mac address.

        Returns:
            str: with six groups of two hexadecimal digits
        """
        return NIC.random_mac()
