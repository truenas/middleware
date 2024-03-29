from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class FTPCertificateAttachment(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'ssltls_certificate'
    HUMAN_NAME = 'FTP Service'
    SERVICE = 'ftp'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', FTPCertificateAttachment(middleware))
