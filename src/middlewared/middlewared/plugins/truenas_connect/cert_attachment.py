from __future__ import annotations

from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class TNCCertificateAttachment(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'certificate'
    HUMAN_NAME = 'TrueNAS Connect Service'
    SERVICE = 'tn_connect'
