from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class TNCCertificateAttachment(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'certificate'
    HUMAN_NAME = 'TrueNAS Connect Service'
    SERVICE = 'tn_connect'


async def setup(middleware: Middleware) -> None:
    await middleware.call('certificate.register_attachment_delegate', TNCCertificateAttachment(middleware))
