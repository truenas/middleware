import errno

from middlewared.api import api_method
from middlewared.api.current import VirtInstanceGetMemoryUsageArgs, VirtInstanceGetMemoryUsageResult
from middlewared.service import CallError, private, Service

from .utils import get_max_requested_memory_of_instance


class VirtInstanceService(Service):

    class Config:
        namespace = 'virt.instance'
        cli_namespace = 'virt.instance'

    async def _set_guest_vmemory(self, vm, overcommit):
        memory_details = await self.middleware.call('virt.instance.get_vm_memory_info', vm['id'])
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
        guest = await self.middleware.call('virt.instance.get_instance', vm) if isinstance(vm, str) else vm
        if guest['status'] == 'STOPPED':
            await self._set_guest_vmemory(guest, overcommit)
        else:
            raise CallError('VM process is running, we won\'t allocate memory')

    @private
    async def teardown_guest_vmemory(self, vm):
        vm = await self.middleware.call('virt.instance.get_instance', vm) if isinstance(vm, str) else vm
        if vm['status'] != 'STOPPED':
            return

        guest_memory = get_max_requested_memory_of_instance(vm)
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

    @api_method(VirtInstanceGetMemoryUsageArgs, VirtInstanceGetMemoryUsageResult, roles=['VIRT_INSTANCE_READ'])
    async def get_memory_usage(self, oid):
        instance_details = await self.middleware.call('virt.instance.get_instance', oid, {'extra': {'raw': True}})
        usage = await self.get_memory_usage_internal(instance_details)
        return {
            'total': get_max_requested_memory_of_instance(instance_details),
            'usage': usage['usage'],
        }

    @private
    async def get_memory_usage_internal(self, instance_details):
        return instance_details['raw'].get('state', {}).get('memory', {}) or {
            'usage': 0,
            'total': 0,
        }


async def _event_virt_instances(middleware, event_type, args):
    instance = await middleware.call('virt.instance.query', [['id', '=', args['id']]])
    status = args.get('fields', {}).get('status')
    if not instance or instance['type'] != 'VM' or instance[0]['status'] != 'STOPPED' or status != 'STOPPED':
        return

    middleware.create_task(middleware.call('virt.instance.teardown_guest_vmemory', instance))


async def setup(middleware):
    middleware.event_subscribe('virt.instance.query', _event_virt_instances)

