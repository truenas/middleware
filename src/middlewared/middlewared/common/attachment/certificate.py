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

    async def state(self, cert_id) -> bool:
        raise NotImplementedError

    async def redeploy(self, cert_id) -> None:
        raise NotImplementedError

    async def consuming_cert_human_output(self, cert_id) -> str | None:
        return self.HUMAN_NAME if await self.state(cert_id) else None


class CertificateServiceAttachmentDelegate(CertificateAttachmentDelegate, ServiceChangeMixin):

    CERT_FIELD = 'certificate'
    SERVICE: str
    SERVICE_VERB = 'RELOAD'

    async def get_namespace(self) -> str:
        return getattr(self, 'NAMESPACE', self.SERVICE)

    async def state(self, cert_id) -> bool:
        config = await self.middleware.call(f'{await self.get_namespace()}.config')
        if isinstance(config[self.CERT_FIELD], dict):
            return config[self.CERT_FIELD]['id'] == cert_id
        else:
            return config[self.CERT_FIELD] == cert_id

    async def redeploy(self, cert_id) -> None:
        if await self.middleware.call('service.started', self.SERVICE):
            await (
                await self.middleware.call('service.control', self.SERVICE_VERB, self.SERVICE)
            ).wait(raise_error=True)


class CertificateCRUDServiceAttachmentDelegate(CertificateAttachmentDelegate, ServiceChangeMixin):

    CERT_FILTER_KEY = 'certificate'

    async def get_filters(self, cert_id) -> list[Any]:
        return [[self.CERT_FILTER_KEY, '=', cert_id]]

    async def attachments(self, cert_id) -> list[Any]:
        return await self.middleware.call(f'{self.NAMESPACE}.query', await self.get_filters(cert_id))

    async def state(self, cert_id) -> bool:
        return bool(await self.attachments(cert_id))
