from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class SystemGeneralCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'ui_certificate'
    NAMESPACE = 'system.general'
    SERVICE = 'http'


class SystemAdvancedCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'syslog_tls_certificate'
    NAMESPACE = 'system.advanced'
    SERVICE = 'syslogd'


async def setup(middleware):
    await middleware.call(
        'certificate.register_attachment_delegate', SystemGeneralCertificateAttachmentDelegate(middleware)
    )
    await middleware.call(
        'certificate.register_attachment_delegate', SystemAdvancedCertificateAttachmentDelegate(middleware)
    )
