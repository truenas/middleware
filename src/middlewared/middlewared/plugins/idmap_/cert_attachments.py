from middlewared.common.attachment.certificate import CertificateCRUDServiceAttachmentDelegate


class IdmapCertificateAttachmentDelegate(CertificateCRUDServiceAttachmentDelegate):

    CERT_FILTER_KEY = 'certificate.id'
    NAMESPACE = 'idmap'

    async def redeploy(self, cert_id):
        pass


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', IdmapCertificateAttachmentDelegate(middleware))
