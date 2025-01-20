from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class TNCCertificateAttachment(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'certificate'
    HUMAN_NAME = 'TrueNAS Connect Service'
    SERVICE = 'tn_connect'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', TNCCertificateAttachment(middleware))
