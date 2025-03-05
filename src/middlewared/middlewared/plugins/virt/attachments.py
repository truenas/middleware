from itertools import product
from typing import TYPE_CHECKING

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.common.ports import PortDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class VirtFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'virt'
    title = 'Virtualization'

    async def query(self, path, enabled, options=None):
        instances = []
        pool = path.split('/')[2] if path.count("/") == 2 else None  # only set if path is pool mp

        for i in await self.middleware.call('virt.instance.query'):
            append = False
            if pool and i['storage_pool'] == pool:
                instances.append({
                    'id': i['id'],
                    'name': i['name'],
                })
                continue

            for device in await self.middleware.call('virt.instance.device_list', i['id']):
                if device['dev_type'] != 'DISK':
                    continue

                if pool and device['storage_pool'] == pool:
                    append = True
                    break

                if device['source'] is None:
                    continue

                if await self.middleware.call('filesystem.is_child', device['source'], path):
                    append = True
                    break

            if append:
                instances.append({
                    'id': i['id'],
                    'name': i['name'],
                })

        return instances

    async def delete(self, attachments):
        if attachments:
            job = await self.middleware.call('virt.global.update', {'pool': None})
            await job.wait(raise_error=True)

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'start' if enabled else 'stop'
            try:
                job = await self.middleware.call(f'virt.instance.{action}', attachment['id'])
                await job.wait(raise_error=True)
            except Exception as e:
                self.middleware.logger.warning('Unable to %s %r: %s', action, attachment['id'], e)

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


class VirtPortDelegate(PortDelegate):

    name = 'virt instances'
    namespace = 'virt'
    title = 'Virtualization Device'

    async def get_ports(self):
        ports = []
        for instance_id, instance_ports in (await self.middleware.call('virt.instance.get_ports_mapping')).items():
            if instance_ports := list(product(['0.0.0.0', '::'], instance_ports)):
                ports.append({
                    'description': f'{instance_id!r} instance',
                    'ports': instance_ports,
                    'instance': instance_id,
                })
        return ports


async def setup(middleware: 'Middleware'):
    middleware.create_task(
        middleware.call(
            'pool.dataset.register_attachment_delegate',
            VirtFSAttachmentDelegate(middleware),
        )
    )
    await middleware.call('port.register_attachment_delegate', VirtPortDelegate(middleware))
