import psutil

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import Service
from middlewared.validators import MACAddr

from .devices import NIC


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
            if status['state'] == 'RUNNING' and guest['autostart'] is False:
                memory_allocation['RNP'] += guest['memory'] * 1024 * 1024
            elif status['state'] == 'RUNNING' and guest['autostart'] is True:
                memory_allocation['RPRD'] += guest['memory'] * 1024 * 1024
            elif guest['autostart']:
                memory_allocation['PRD'] += guest['memory'] * 1024 * 1024

        return memory_allocation

    @accepts(Bool('overcommit', default=False))
    @returns(Int('available_memory'))
    async def get_available_memory(self, overcommit):
        """
        Get the current maximum amount of available memory to be allocated for VMs.

        If `overcommit` is true only the current used memory of running VMs will be accounted for.
        If false all memory (including unused) of runnings VMs will be accounted for.

        This will include memory shrinking ZFS ARC to the minimum.

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

        vms_memory_used = 0
        if overcommit is False:
            # If overcommit is not wanted its verified how much physical memory
            # the vm process is currently using and add the maximum memory its
            # supposed to have.
            for vm in await self.middleware.call('vm.query'):
                if vm['status']['state'] == 'RUNNING':
                    try:
                        vms_memory_used += await self.middleware.call('vm.get_memory_usage_internal', vm)
                    except Exception:
                        self.logger.error('Unable to retrieve %r vm memory usage', vm['name'], exc_info=True)
                        continue

        return max(0, free + arc_shrink - vms_memory_used - swap_used)

    @accepts()
    @returns(Str('mac', validators=[MACAddr(separator=':')]),)
    def random_mac(self):
        """
        Create a random mac address.

        Returns:
            str: with six groups of two hexadecimal digits
        """
        return NIC.random_mac()
