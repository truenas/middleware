from middlewared.service import (
    CallError, CRUDService, ValidationErrors, filterable, job
)
from middlewared.utils import filter_list

from middlewared.api import api_method
from middlewared.api.current import (
    VirtInstanceEntry,
    VirtInstanceCreateArgs, VirtInstanceCreateResult,
    VirtInstanceUpdateArgs, VirtInstanceUpdateResult,
    VirtInstanceDeleteArgs, VirtInstanceDeleteResult,
    VirtInstanceStateArgs, VirtInstanceStateResult,
)
from .utils import incus_call, incus_call_and_wait


class VirtInstancesService(CRUDService):

    class Config:
        namespace = 'virt.instances'
        cli_namespace = 'virt.instances'
        entry = VirtInstanceEntry

    @filterable
    async def query(self, filters, options):
        """
        Query all VirtInstances with `query-filters` and `query-options`.
        """
        results = (await incus_call('1.0/instances?filter=&recursion=2', 'get'))['metadata']
        entries = []
        for i in results:
            entry = {
                'id': i['name'],
                'raw': i,
                'status': i['state']['status'].upper(),
            }
            entries.append(entry)
        return filter_list(entries, filters, options)

    @api_method(VirtInstanceCreateArgs, VirtInstanceCreateResult)
    @job()
    async def do_create(self, job, data):
        """
        """
        async def running_cb(data):
            if 'metadata' in data['metadata'] and (metadata := data['metadata']['metadata']):
                if 'download_progress' in metadata:
                    job.set_progress(None, metadata['download_progress'])
                if 'create_instance_from_image_unpack_progress' in metadata:
                    job.set_progress(None, metadata['create_instance_from_image_unpack_progress'])

        await incus_call_and_wait('1.0/instances', 'post', {'json': {
            'name': data['name'],
            'ephemeral': False,
            'source': {
                'type': 'image',
                'server': 'https://images.linuxcontainers.org',
                'protocol': 'simplestreams',
                'mode': 'pull',
                'alias': data['image'],
            },
            'type': 'container',
            'start': True,
        }}, running_cb)

        return await self.middleware.call('virt.instances.get_instance', data['name'])

    @api_method(VirtInstanceUpdateArgs, VirtInstanceUpdateResult)
    @job()
    async def do_update(self, job, id, data):
        """
        """
        instance = await self.middleware.call('virt.instances.get_instance', id)
        if instance['status'] == 'Running':
            config = instance['config']
            if 'limits_config' in data:
                config['limits.memory'] = data['limits_config']
            await incus_call_and_wait(f'1.0/instances/{id}', 'put', {'json': instance})

        return await self.middleware.call('virt.instances.get_instance', id)

    @api_method(VirtInstanceDeleteArgs, VirtInstanceDeleteResult)
    @job()
    async def do_delete(self, job, id):
        """
        """
        instance = await self.middleware.call('virt.instances.get_instance', id)
        if instance['status'] == 'Running':
            await self._call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
                'action': 'stop',
                'timeout': -1,
                'force': True,
            }})

        await incus_call_and_wait(f'1.0/instances/{id}', 'delete')

        return True

    @api_method(VirtInstanceStateArgs, VirtInstanceStateResult)
    @job()
    async def state(self, job, id, action, force):
        """
        """
        await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
            'action': action.lower(),
            'timeout': -1,
            'force': force,
        }})

        return True
