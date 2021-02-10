from middlewared.service import private, Service


class CertificateService(Service):

    class Config:
        cli_namespace = 'system.certificate'

    @private
    async def services_dependent_on_cert(self, id):
        await self.middleware.call('certificate.get_instance', id)
        services = await self.middleware.call('core.get_services')
        dependents = {
            'services': [],
            'chart_releases': [
                c['id'] for c in await self.middleware.call(
                    'chart.release.query', [['resources.truenas_certificates', 'rin', id]], {
                        'extra': {'retrieve_resources': True}
                    }
                )
            ],
        }
        for svc_name in map(
            lambda d: d['service'], filter(
                lambda d: d['service'] in services,
                (await self.middleware.call('certificate.get_dependencies', id)).values()
            )
        ):
            svc = services[svc_name]
            data = {}
            if svc_name == 'system.general':
                data = {'action': 'reload', 'service': 'http'}
            elif svc_name == 'system.advanced':
                data = {'action': 'reload', 'service': 'syslogd'}
            elif svc_name == 'kmip':
                data = {'action': 'start', 'service': 'kmip'}
            elif svc_name == 'ldap':
                data = {'action': 'start', 'service': 'ldap'}
            elif svc['config']['service']:
                data = {
                    'action': svc['config']['service_verb'] or 'reload', 'service': svc['config']['service']
                }

            if data:
                dependents['services'].append(data)

        return dependents

    @private
    async def reload_cert_dependent_services(self, id):
        dependents = await self.services_dependent_on_cert(id)
        for action in dependents['services']:
            if not await self.middleware.call('service.started', action['service']):
                # If the service is not already started, we are not going to reload/restart it
                continue

            try:
                await self.middleware.call(f'service.{action["action"]}', action['service'])
            except Exception:
                self.logger.error('Failed to %r %s service', action['action'], action['service'], exc_info=True)

        bulk_job = await self.middleware.call(
            'core.bulk', 'chart.release.redeploy', [[chart_release] for chart_release in dependents['chart_releases']]
        )
        for index, status in enumerate(await bulk_job.wait()):
            if status['error']:
                self.logger.error(
                    'Failed to redeploy %r chart release: %s', dependents['chart_releases'][index], status['error']
                )
