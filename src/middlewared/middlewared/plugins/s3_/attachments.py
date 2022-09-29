import os

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate
from middlewared.common.ports import ServicePortDelegate
from middlewared.utils.path import is_child


class MinioFSAttachmentDelegate(FSAttachmentDelegate):
    name = 's3'
    title = 'S3'
    service = 's3'

    async def query(self, path, enabled, options=None):
        results = []

        s3_config = await self.middleware.call('s3.config')
        if not s3_config['storage_path'] or not os.path.exists(s3_config['storage_path']):
            return []

        try:
            s3_ds = await self.middleware.call('zfs.dataset.path_to_dataset', s3_config['storage_path'])
        except Exception:
            self.middleware.logger.warning('%s: failed to look up dataset', s3_config['storage_path'], exc_info=True)
            return []

        if is_child(os.path.join('/mnt', s3_ds), path):
            results.append({'id': s3_ds})

        return results

    async def get_attachment_name(self, attachment):
        return attachment['id']

    async def delete(self, attachments):
        await self.stop(attachments)
        await self.middleware.call('s3.update', {'storage_path': ''})

    async def toggle(self, attachments, enabled):
        await getattr(self, 'start' if enabled else 'stop')(attachments)

    async def stop(self, attachments):
        try:
            await self.middleware.call('service.stop', 's3')
        except Exception:
            self.middleware.logger.error('Failed to stop s3', exc_info=True)

    async def start(self, attachments):
        try:
            await self.middleware.call('service.start', 's3')
        except Exception:
            self.middleware.logger.error('Failed to start s3', exc_info=True)


class S3CertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    SERVICE = 's3'


class S3ServicePortDelegate(ServicePortDelegate):

    port_fields = ['bindport', 'console_bindport']
    service = 's3'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', S3CertificateAttachmentDelegate(middleware))
    await middleware.call('pool.dataset.register_attachment_delegate', MinioFSAttachmentDelegate(middleware))
    await middleware.call('port.register_attachment_delegate', S3ServicePortDelegate(middleware))
