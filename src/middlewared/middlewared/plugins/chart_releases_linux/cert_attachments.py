from middlewared.common.attachment.certificate import CertificateCRUDServiceAttachmentDelegate
from middlewared.service import private, Service


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
        # We use chart.release.update as here we want the configuration to be refreshed as well
        # in this specific case that being getting the renewed certificate
        bulk_job = await self.middleware.call(
            'core.bulk', 'chart.release.update', [[r, {'values': {}}] for r in await self.attachments(cert_id)]
        )
        for index, status in enumerate(await bulk_job.wait()):
            if status['error']:
                self.middleware.logger.error(
                    'Failed to redeploy %r chart release: %s', chart_releases[index], status['error']
                )


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def get_chart_releases_consuming_outdated_certs(self, filters=None):
        chart_releases = []
        filters = filters or []
        certs = {c['id']: c for c in await self.middleware.call('certificate.query')}
        for chart_release in await self.middleware.call('chart.release.query', filters):
            for cert_id, cert in filter(
                lambda v: int(v[0]) in certs, chart_release['config'].get('ixCertificates', {}).items()
            ):
                cert_id = int(cert_id)
                if cert['certificate'] != certs[cert_id]['certificate']:
                    chart_releases.append(chart_release['id'])
                    break
        return chart_releases
