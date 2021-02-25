from middlewared.common.attachment.certificate import CertificateCRUDServiceAttachmentDelegate


class ChartReleaseCertificateAttachmentDelegate(CertificateCRUDServiceAttachmentDelegate):

    NAMESPACE = 'chart.release'

    async def get_filters(self, cert_id):
        return [['resources.truenas_certificates', 'rin', cert_id]]

    async def attachments(self, cert_id):
        return await self.middleware.call(
            f'{self.NAMESPACE}.query', await self.get_filters(cert_id), {'extra': {'retrieve_resources': True}}
        )

    async def redeploy(self, cert_id):
        chart_releases = [r['name'] for r in await self.attachments(cert_id)]
        bulk_job = await self.middleware.call(
            'core.bulk', 'chart.release.redeploy', [[r] for r in await self.attachments(cert_id)]
        )
        for index, status in enumerate(await bulk_job.wait()):
            if status['error']:
                self.middleware.logger.error(
                    'Failed to redeploy %r chart release: %s', chart_releases[index], status['error']
                )
