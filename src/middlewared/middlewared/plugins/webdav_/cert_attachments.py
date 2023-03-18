from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class WebdavCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'certssl'
    HUMAN_NAME = 'Webdav Service'
    SERVICE = 'webdav'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', WebdavCertificateAttachmentDelegate(middleware))
