from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate
from middlewared.common.ports import ServicePortDelegate


class KmipCertificateAttachment(CertificateServiceAttachmentDelegate):

    SERVICE = 'kmip'
    SERVICE_VERB = 'start'


class KMIPServicePortDelegate(ServicePortDelegate):

    name = 'kmip'
    namespace = 'kmip'
    port_fields = ['port']
    title = 'KMIP Service'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', KmipCertificateAttachment(middleware))
    await middleware.call('port.register_attachment_delegate', KMIPServicePortDelegate(middleware))
