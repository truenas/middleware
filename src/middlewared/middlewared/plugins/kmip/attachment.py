from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class KmipCertificateAttachment(CertificateServiceAttachmentDelegate):

    SERVICE = 'kmip'
    SERVICE_VERB = 'start'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', KmipCertificateAttachment(middleware))
