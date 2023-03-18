from middlewared.service import CallError, Service


class CertificateAuthorityService(Service):

    class Config:
        cli_namespace = 'system.certificate.authority'

    async def check_ca_dependencies(self, ca_id):
        await self.middleware.call('certificateauthority.check_dependencies', ca_id)
        chart_releases = await self.middleware.call(
            'chart.release.query', [
                [f'resources.truenas_certificate_authorities', 'rin', ca_id]
            ], {'extra': {'retrieve_resources': True}}
        )
        if chart_releases:
            raise CallError(
                f'Certificate Authority cannot be deleted as it is being used by '
                f'{", ".join([c["id"] for c in chart_releases])} chart release(s).'
            )


def check_dependencies(middleware, cert_type, id):
    if cert_type == 'CA':
        key = 'truenas_certificate_authorities'
        middleware.call_sync('certificateauthority.check_dependencies', id)
    else:
        key = 'truenas_certificates'

        method = 'certificate.check_dependencies'

    middleware.call_sync(method, id)

    chart_releases = middleware.call_sync(
        'chart.release.query', [[f'resources.{key}', 'rin', id]], {'extra': {'retrieve_resources': True}}
    )
    if chart_releases:
        raise CallError(
            f'Certificate{" Authority" if cert_type == "CA" else ""} cannot be deleted as it is being used by '
            f'{", ".join([c["id"] for c in chart_releases])} chart release(s).'
        )
