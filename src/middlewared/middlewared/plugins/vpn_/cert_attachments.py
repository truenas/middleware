from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class OpenvpnServerCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'server_certificate'
    HUMAN_NAME = 'OpenVPN Server Service'
    NAMESPACE = 'openvpn.server'
    SERVICE = 'openvpn_server'


class OpenvpnClientCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'client_certificate'
    HUMAN_NAME = 'OpenVPN Client Service'
    NAMESPACE = 'openvpn.client'
    SERVICE = 'openvpn_client'


async def setup(middleware):
    await middleware.call(
        'certificate.register_attachment_delegate', OpenvpnServerCertificateAttachmentDelegate(middleware)
    )
    await middleware.call(
        'certificate.register_attachment_delegate', OpenvpnClientCertificateAttachmentDelegate(middleware)
    )
