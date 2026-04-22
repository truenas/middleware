from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.common.attachment.certificate import CertificateCRUDServiceAttachmentDelegate
from middlewared.service import Service

from .ix_apps.metadata import get_collective_config

if TYPE_CHECKING:
    from middlewared.api.current import AppEntry
    from middlewared.main import Middleware


class AppCertificateAttachmentDelegate(CertificateCRUDServiceAttachmentDelegate):

    HUMAN_NAME = 'Applications'
    NAMESPACE = 'app'

    async def consuming_cert_human_output(self, cert_id: int) -> str | None:
        attachments = await self.attachments(cert_id)
        return f'{", ".join(app.id for app in attachments)!r} {self.HUMAN_NAME}' if attachments else None

    async def attachments(self, cert_id: int) -> list[AppEntry]:
        config = await self.middleware.run_in_thread(get_collective_config)
        apps_consuming_cert = [
            app_name for app_name, app_config in config.items() if cert_id in app_config.get('ix_certificates', {})
        ]
        return await self.call2(self.s.app.query, [['id', 'in', apps_consuming_cert]])

    async def redeploy(self, cert_id: int) -> None:
        apps = [r.name for r in await self.attachments(cert_id)]
        bulk_job = await self.middleware.call('core.bulk', 'app.redeploy', [[app] for app in apps])
        for index, status in enumerate(await bulk_job.wait()):
            if status['error']:
                self.middleware.logger.error(
                    'Failed to redeploy %r app: %s', apps[index], status['error']
                )


class AppCertificateService(Service):

    class Config:
        namespace = 'app.certificate'
        private = True

    async def get_apps_consuming_outdated_certs(self, filters: list[Any] | None = None) -> list[str]:
        apps_having_outdated_certs = []
        filters = filters or []
        certs = {c['id']: c for c in await self.middleware.call('certificate.query')}
        config = await self.middleware.run_in_thread(get_collective_config)
        apps = {app.name: app for app in await self.call2(self.s.app.query, filters)}
        for app_name, app_config in config.items():
            if app_name not in apps or not app_config.get('ix_certificates'):
                continue

            if any(
                cert['certificate'] != certs[cert_id]['certificate']
                for cert_id, cert in app_config['ix_certificates'].items()
                if cert_id in certs
            ):
                apps_having_outdated_certs.append(app_name)

        return apps_having_outdated_certs

    async def redeploy_apps_consuming_outdated_certs(self) -> Any:
        return await self.middleware.call(
            'core.bulk', 'app.redeploy', [[r] for r in await self.get_apps_consuming_outdated_certs()]
        )


async def setup(middleware: Middleware) -> None:
    await middleware.call(
        'certificate.register_attachment_delegate', AppCertificateAttachmentDelegate(middleware)
    )
