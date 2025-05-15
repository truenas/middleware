# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate
from middlewared.common.ports import ServicePortDelegate


class KmipCertificateAttachment(CertificateServiceAttachmentDelegate):

    HUMAN_NAME = 'KMIP Service'
    SERVICE = 'kmip'
    SERVICE_VERB = 'START'


class KMIPServicePortDelegate(ServicePortDelegate):

    name = 'kmip'
    namespace = 'kmip'
    port_fields = ['port']
    title = 'KMIP Service'


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', KmipCertificateAttachment(middleware))
    await middleware.call('port.register_attachment_delegate', KMIPServicePortDelegate(middleware))
