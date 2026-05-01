from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    CertificateCreate,
    CertificateCreateArgs,
    CertificateCreateResult,
    CertificateDeleteArgs,
    CertificateDeleteResult,
    CertificateEntry,
    CertificateUpdate,
    CertificateUpdateArgs,
    CertificateUpdateResult,
)
from middlewared.service import GenericCRUDService, job, private

from .attachment_delegate import (
    get_attachments,
    in_use_attachments,
    redeploy_cert_attachments,
    register_attachment_delegate,
)
from .crud import CertificateServicePart

if TYPE_CHECKING:
    from middlewared.common.attachment.certificate import CertificateAttachmentDelegate
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('CertificateService',)


class CertificateService(GenericCRUDService[CertificateEntry]):

    class Config:
        cli_namespace = 'system.certificate'
        role_prefix = 'CERTIFICATE'
        entry = CertificateEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = CertificateServicePart(self.context)

    @api_method(CertificateCreateArgs, CertificateCreateResult, check_annotations=True)
    @job(lock='cert_create')
    async def do_create(self, job: Job, data: CertificateCreate) -> CertificateEntry:
        """
        Create a new Certificate

        Certificates are classified under following types and the necessary keywords to be passed
        for `create_type` attribute to create the respective type of certificate

        1) Imported Certificate                 -  CERTIFICATE_CREATE_IMPORTED

        2) Certificate Signing Request          -  CERTIFICATE_CREATE_CSR

        3) Imported Certificate Signing Request -  CERTIFICATE_CREATE_IMPORTED_CSR

        4) ACME Certificate                     -  CERTIFICATE_CREATE_ACME

        By default, created CSRs use RSA keys. If an Elliptic Curve Key is desired, it can be specified with the
        `key_type` attribute. If the `ec_curve` attribute is not specified for the Elliptic Curve Key, then default to
        using "SECP384R1" curve.

        A type is selected by the Certificate Service based on `create_type`. The rest of the values in `data` are
        validated accordingly and finally a certificate is made based on the selected type.
        """
        return await self._svc_part.do_create(job, data)

    @api_method(CertificateUpdateArgs, CertificateUpdateResult, check_annotations=True)
    @job(lock='cert_update')
    async def do_update(self, job: Job, id_: int, data: CertificateUpdate) -> CertificateEntry:
        """Update certificate of `id`."""
        return await self._svc_part.do_update(job, id_, data)

    @api_method(CertificateDeleteArgs, CertificateDeleteResult, check_annotations=True)
    @job(lock='cert_delete')
    def do_delete(self, job: Job, id_: int, force: bool) -> bool:
        """
        Delete certificate of `id`.

        If the certificate is an ACME based certificate, certificate service will try to
        revoke the certificate by updating it's status with the ACME server, if it fails an exception is raised
        and the certificate is not deleted from the system. However, if `force` is set to True, certificate is deleted
        from the system even if some error occurred while revoking the certificate with the ACME Server.
        """
        return self._svc_part.do_delete(job, id_, force)

    @private
    async def get_attachments(self, cert_id: int) -> list[str | None]:
        return await get_attachments(cert_id)

    @private
    async def in_use_attachments(self, cert_id: int) -> list[CertificateAttachmentDelegate]:
        return await in_use_attachments(cert_id)

    @private
    async def redeploy_cert_attachments(self, cert_id: int) -> None:
        await redeploy_cert_attachments(cert_id)

    @private
    async def register_attachment_delegate(self, delegate: CertificateAttachmentDelegate) -> None:
        register_attachment_delegate(delegate)
