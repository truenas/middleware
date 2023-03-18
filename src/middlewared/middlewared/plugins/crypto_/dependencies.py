from middlewared.service import CallError, private, Service


class CertificateService(Service):

    @private
    async def check_cert_deps(self, cert_id):
        if deps := await self.middleware.call('certificate.get_attachments', cert_id):
            deps_str = ''
            for i, svc in enumerate(deps):
                deps_str += f'{i+1}) {svc}\n'
            raise CallError(f'Certificate is being used by following service(s):\n{deps_str}')


class CertificateAuthorityService(Service):

    class Config:
        cli_namespace = 'system.certificate.authority'

    @private
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
