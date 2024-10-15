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

    async def delete(self, attachments):
        ''' Delete NFS shares
        The attachments is a list of shares exporting a pool that is being deleted'''
        for attachment in attachments:
            self.logger.debug(f"[MCG DEBUG] delete share: {attachment}")
            await self.middleware.call('sharing.nfs.delete', attachment['id'])

        # Every share delete includes a reload.  Let's do one extra for good measure.
        await self._service_change('nfs', 'reload')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', NFSFSAttachmentDelegate(middleware))
