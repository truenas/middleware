from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.service import ServiceChangeMixin

if TYPE_CHECKING:
    from middlewared.main import Middleware


class CertificateAttachmentDelegate:

    HUMAN_NAME: str
    NAMESPACE: str

    def __init__(self, middleware: Middleware) -> None:
        self.middleware = middleware

    async def state(self, cert_id: int) -> bool:
        raise NotImplementedError

    async def redeploy(self, cert_id: int) -> None:
        raise NotImplementedError

    async def consuming_cert_human_output(self, cert_id: int) -> str | None:
        return self.HUMAN_NAME if await self.state(cert_id) else None


class CertificateServiceAttachmentDelegate(CertificateAttachmentDelegate, ServiceChangeMixin):

    CERT_FIELD = 'certificate'
    SERVICE: str
    SERVICE_VERB = 'RELOAD'

    async def get_namespace(self) -> str:
        return getattr(self, 'NAMESPACE', self.SERVICE)

    async def state(self, cert_id: int) -> bool:
        # Config can be either a dict (legacy/unconverted services) or a Pydantic model
        # (typesafe services with `generic = True`, e.g. tn_connect). Dispatch field
        # access accordingly.
        config = await self.middleware.call(f'{await self.get_namespace()}.config')
        cert_value = config[self.CERT_FIELD] if isinstance(config, dict) else getattr(config, self.CERT_FIELD)
        if isinstance(cert_value, dict):
            return cert_value['id'] == cert_id  # type: ignore[no-any-return]
        return cert_value == cert_id  # type: ignore[no-any-return]

    async def redeploy(self, cert_id: int) -> None:
        if await self.middleware.call('service.started', self.SERVICE):
            await (
                await self.middleware.call('service.control', self.SERVICE_VERB, self.SERVICE)
            ).wait(raise_error=True)


class CertificateCRUDServiceAttachmentDelegate[E](CertificateAttachmentDelegate, ServiceChangeMixin):

    CERT_FILTER_KEY = 'certificate'

    async def get_filters(self, cert_id: int) -> list[Any]:
        return [[self.CERT_FILTER_KEY, '=', cert_id]]

    async def attachments(self, cert_id: int) -> list[E]:
        return await self.middleware.call(  # type: ignore[no-any-return]
            f'{self.NAMESPACE}.query',
            await self.get_filters(cert_id),
        )

    async def state(self, cert_id: int) -> bool:
        return bool(await self.attachments(cert_id))
