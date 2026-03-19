from __future__ import annotations

import errno

from middlewared.api.current import VMGetVmemoryInUse, VMGetVmMemoryInfo
from middlewared.service import CallError, ServiceContext
from middlewared.utils.libvirt.utils import ACTIVE_STATES
from middlewared.utils.memory import get_memory_info


def get_memory_usage_internal(context: ServiceContext, vm_uuid: str) -> int | None:
    libvirt_domain = context.middleware.libvirt_domains_manager.vms_connection.get_domain(vm_uuid)
    if libvirt_domain is None:
        return None
    else:
        return int(context.middleware.libvirt_domains_manager.vms_connection.domain_memory_usage(libvirt_domain))


def get_memory_usage(context: ServiceContext, vm_id: int) -> int:
    return get_memory_usage_internal(
        context,
        context.middleware.call_sync('datastore.query', 'vm.vm', [['id', '=', vm_id]], {'get': True})['uuid']
    ) or 0


async def get_vmemory_in_use(context: ServiceContext) -> VMGetVmemoryInUse:
    memory_allocation = {'RNP': 0, 'PRD': 0, 'RPRD': 0}
    for guest in await context.call2(context.s.vm.query):
        if guest.status.state in ACTIVE_STATES:
            memory_allocation['RPRD' if guest.autostart else 'RNP'] += guest.memory * 1024 * 1024
        elif guest.autostart:
            memory_allocation['PRD'] += guest.memory * 1024 * 1024

    return VMGetVmemoryInUse(**memory_allocation)


async def get_available_memory(context: ServiceContext, overcommit: bool) -> int:
    # Use 90% of available memory to play safe
    free = int((await context.to_thread(get_memory_info))['available'] * 0.9)

    # Difference between current ARC total size and the minimum allowed
    arc_total = await context.middleware.call('sysctl.get_arcstats_size')
    arc_min = await context.middleware.call('sysctl.get_arc_min')
    arc_shrink = max(0, arc_total - arc_min)
    total_free = free + arc_shrink

    vms_memory_used = 0
    if overcommit is False:
        # If overcommit is not wanted its verified how much physical memory
        # the vm process is currently using and add the maximum memory its
        # supposed to have.
        for vm in await context.call2(context.s.vm.query):
            if vm.status.state not in ACTIVE_STATES:
                continue
            try:
                current_vm_mem = await context.to_thread(get_memory_usage_internal, context, vm.uuid)
                if current_vm_mem is None:
                    # We only account for running VMs
                    continue
            except Exception:
                context.logger.error('Unable to retrieve %r vm memory usage', vm.name, exc_info=True)
                continue
            else:
                vm_max_mem = vm.memory * 1024 * 1024
                # We handle edge case with vm_max_mem < current_vm_mem
                if vm_max_mem > current_vm_mem:
                    vms_memory_used += vm_max_mem - current_vm_mem

    return int(max(0, total_free - vms_memory_used))


async def get_vm_memory_info(context: ServiceContext, vm_id: int) -> VMGetVmMemoryInfo:
    vm = await context.call2(context.s.vm.get_instance, vm_id)
    if vm.status.state in ACTIVE_STATES:
        # TODO: Let's add this later as we have a use case in the UI - could be useful to
        #  show separate info of each VM in the UI moving on
        raise CallError(f'Unable to retrieve {vm.name!r} VM information as it is already running.')

    arc_max = await context.middleware.call('sysctl.get_arc_max')
    arc_min = await context.middleware.call('sysctl.get_arc_min')
    shrinkable_arc_max = max(0, arc_max - arc_min)

    available_memory = await get_available_memory(context, False)
    available_memory_with_overcommit = await get_available_memory(context, True)
    vm_max_memory = vm.memory * 1024 * 1024
    vm_min_memory = vm.min_memory * 1024 * 1024 if vm.min_memory else None
    vm_requested_memory = vm_min_memory or vm_max_memory

    overcommit_required = vm_requested_memory > available_memory
    arc_to_shrink = 0
    if overcommit_required:
        arc_to_shrink = min(shrinkable_arc_max, vm_requested_memory - available_memory)

    return VMGetVmMemoryInfo(
        minimum_memory_requested=vm_min_memory,
        total_memory_requested=vm_max_memory,
        overcommit_required=overcommit_required,
        arc_to_shrink=arc_to_shrink,
        memory_req_fulfilled_after_overcommit=vm_requested_memory < available_memory_with_overcommit,
        current_arc_max=arc_max,
        arc_min=arc_min,
        arc_max_after_shrink=arc_max - arc_to_shrink,
        actual_vm_requested_memory=vm_requested_memory,
    )


async def _set_guest_vmemory(context: ServiceContext, vm_id: int, overcommit: bool) -> None:
    vm = await context.call2(context.s.vm.get_instance, vm_id)
    memory_details = await get_vm_memory_info(context, vm_id)
    if not memory_details.overcommit_required:
        # There really isn't anything to be done if over-committing is not required
        return

    if not overcommit:
        raise CallError(f'Cannot guarantee memory for guest {vm.name}', errno.ENOMEM)

    if memory_details.current_arc_max != memory_details.arc_max_after_shrink:
        context.logger.debug(
            'Setting ARC from %s to %s', memory_details.current_arc_max, memory_details.arc_max_after_shrink
        )
        await context.middleware.call('sysctl.set_arc_max', memory_details.arc_max_after_shrink)


async def init_guest_vmemory(context: ServiceContext, vm_id: int, overcommit: bool) -> None:
    guest = await context.call2(context.s.vm.get_instance, vm_id)
    if guest.status.state not in ACTIVE_STATES:
        await _set_guest_vmemory(context, vm_id, overcommit)
    else:
        raise CallError('VM process is already running, memory will not be allocated')


async def teardown_guest_vmemory(context: ServiceContext, vm_id: int) -> None:
    vm = await context.call2(context.s.vm.get_instance, vm_id)
    if vm.status.state != 'STOPPED':
        return

    guest_memory = vm.memory * 1024 * 1024
    arc_max = await context.middleware.call('sysctl.get_arc_max')
    arc_min = await context.middleware.call('sysctl.get_arc_min')
    new_arc_max = min(
        await context.middleware.call('sysctl.get_default_arc_max'),
        arc_max + guest_memory
    )
    if arc_max != new_arc_max:
        if new_arc_max > arc_min:
            context.logger.debug(f'Giving back guest memory to ARC: {new_arc_max}')
            await context.middleware.call('sysctl.set_arc_max', new_arc_max)
        else:
            context.logger.warn(
                f'Not giving back memory to ARC because new arc_max ({new_arc_max}) <= arc_min ({arc_min})'
            )
