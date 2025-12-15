from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.nvmet.namespace import NVMetNamespaceService


class NVMetNamespaceAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'nvmet'
    title = 'NVMe-oF Namespace'
    service = 'nvmet'
    service_class = NVMetNamespaceService
    resource_name = 'device_path'

    async def restart_reload_services(self, attachments):
        await self.middleware.call('nvmet.global.reload')

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'start' if enabled else 'stop'
            try:
                await self.middleware.call(f'nvmet.namespace.{action}', attachment['id'])
            except Exception as e:
                self.middleware.logger.warning('Unable to %s %r: %s', action, attachment['id'], e)

    async def stop(self, attachments, options=None):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', NVMetNamespaceAttachmentDelegate(middleware))
