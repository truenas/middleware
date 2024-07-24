from typing import TYPE_CHECKING
from middlewared.common.attachment import FSAttachmentDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class VirtFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'virt'
    title = 'Virtualization'

    async def query(self, path, enabled, options=None):
        config = await self.middleware.call('virt.global.config')
        instances = []
        for i in await self.middleware.call('virt.instances.query'):
            append = False
            if path != f'/mnt/{config["pool"]}':
                for device in await self.middleware.call('virt.instances.device_list', i['id']):
                    if device['dev_type'] != 'DISK':
                        continue
                    if device['source'] is None:
                        continue
                    if await self.middleware.call('filesystem.is_child', device['source'], path):
                        append = True
                        break

            else:
                append = True
            if append:
                instances.append({
                    'id': i['id'],
                    'name': i['name'],
                })
        return instances

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                job = await self.middleware.call('virt.instances.state', attachment['id'], 'STOP')
                await job.wait(raise_error=True)
            except Exception as e:
                self.middleware.logger.warning('Unable to stop %r: %s', attachment['id'], e)

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'START' if enabled else 'STOP'
            try:
                job = await self.middleware.call('virt.instances.state', attachment['id'], action)
                await job.wait(raise_error=True)
            except Exception as e:
                self.middleware.logger.warning('Unable to %s %r: %s', action, attachment['id'], e)

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


async def setup(middleware: 'Middleware'):
    middleware.create_task(
        middleware.call(
            'pool.dataset.register_attachment_delegate',
            VirtFSAttachmentDelegate(middleware),
        )
    )
