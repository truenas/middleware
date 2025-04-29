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
        dataset = path.removeprefix('/mnt/')

        for i in await self.middleware.call('virt.instance.query'):
            append = False
            if pool and i['storage_pool'] == pool:
                instances.append({
                    'id': i['id'],
                    'name': i['name'],
                    'disk_devices': [],
                    'dataset': dataset,
                })
                continue

            disks = []
            for device in await self.middleware.call('virt.instance.device_list', i['id']):
                if device['dev_type'] != 'DISK':
                    continue

                if pool and device['storage_pool'] == pool:
                    append = True
                    disks.append(device['name'])
                    continue

                if device['source'] is None:
                    continue

                source_path = device['source'].removeprefix('/dev/zvol/').removeprefix('/mnt/')
                if await self.middleware.call('filesystem.is_child', source_path, dataset):
                    append = True
                    disks.append(device['name'])
                    continue

            if append:
                instances.append({
                    'id': i['id'],
                    'name': i['name'],
                    'disk_devices': disks,
                    'dataset': dataset,
                })

        return instances

    async def delete(self, attachments):
        virt_config = await self.middleware.call('virt.global.config')
        if not attachments or any(
            virt_config['pool'] == attachment['dataset'] for attachment in attachments
        ):
            # If there are no attachments or if any attachment we have the virt pool
            # being removed we should not do anything here
            return

        disks_to_remove = [i for i in filter(lambda i: i.get('disk_devices'), attachments)]
        for instance_data in disks_to_remove:
            for to_remove_disk in instance_data['disk_devices']:
                await self.middleware.call('virt.instance.device_delete', instance_data['name'], to_remove_disk)

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
