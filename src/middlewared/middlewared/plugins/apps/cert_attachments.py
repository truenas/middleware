from middlewared.common.attachment.certificate import CertificateCRUDServiceAttachmentDelegate

from .ix_apps.metadata import get_collective_config


class AppCertificateAttachmentDelegate(CertificateCRUDServiceAttachmentDelegate):

    HUMAN_NAME = 'Applications'
    NAMESPACE = 'app'

    async def consuming_cert_human_output(self, cert_id):
        attachments = await self.attachments(cert_id)
        return f'{", ".join(app["id"] for app in attachments)!r} {self.HUMAN_NAME}' if attachments else None

    async def attachments(self, cert_id):
        config = await self.middleware.run_in_thread(get_collective_config)
        apps_consuming_cert = [
            app_name for app_name, app_config in config.items() if cert_id in app_config.get('ix_certificates', {})
        ]
        return await self.middleware.call(f'{self.NAMESPACE}.query', [['id', 'in', apps_consuming_cert]])

    async def redeploy(self, cert_id):
        apps = [r['name'] for r in await self.attachments(cert_id)]
        bulk_job = await self.middleware.call('core.bulk', 'app.redeploy', [[app] for app in apps])
        for index, status in enumerate(await bulk_job.wait()):
            if status['error']:
                self.middleware.logger.error(
                    'Failed to redeploy %r app: %s', apps[index], status['error']
                )


async def setup(middleware):
    await middleware.call(
        'certificate.register_attachment_delegate', AppCertificateAttachmentDelegate(middleware)
    )
