from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class LdapCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    HUMAN_NAME = 'LDAP Service'
    SERVICE = 'ldap'
    SERVICE_VERB = 'start'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', LdapCertificateAttachmentDelegate(middleware))
