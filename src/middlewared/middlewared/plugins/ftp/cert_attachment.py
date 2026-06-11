from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class FTPCertificateAttachment(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'ssltls_certificate'
    HUMAN_NAME = 'FTP Service'
    SERVICE = 'ftp'


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.certificate.register_attachment_delegate,
        FTPCertificateAttachment(middleware),
    )
