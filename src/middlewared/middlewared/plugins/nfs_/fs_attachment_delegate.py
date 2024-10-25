from middlewared.common.attachment import LockableFSAttachmentDelegate

from middlewared.plugins.nfs import SharingNFSService


class NFSFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'nfs'
    title = 'NFS Share'
    service = 'nfs'
    service_class = SharingNFSService
    resource_name = 'path'

    async def restart_reload_services(self, attachments):
        await self._service_change('nfs', 'reload')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', NFSFSAttachmentDelegate(middleware))
