# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate
from middlewared.common.ports import ServicePortDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class KmipCertificateAttachment(CertificateServiceAttachmentDelegate):

    HUMAN_NAME = 'KMIP Service'
    SERVICE = 'kmip'
    SERVICE_VERB = 'START'


class KMIPServicePortDelegate(ServicePortDelegate):

    name = 'kmip'
    namespace = 'kmip'
    port_fields = ['port']
    title = 'KMIP Service'

    async def config(self) -> dict[str, Any]:
        return (await self.middleware.call2(self.middleware.services.kmip.config)).model_dump()


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.certificate.register_attachment_delegate,
        KmipCertificateAttachment(middleware),
    )
    await middleware.call('port.register_attachment_delegate', KMIPServicePortDelegate(middleware))
