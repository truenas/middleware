from middlewared.schema import Str
from middlewared.service import accepts, private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def retrieve_pod_with_containers(self, release_name):
        await self.middleware.call('kubernetes.validate_k8s_setup')
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        choices = {}
        for pod in release['resources']['pods']:
            choices[pod['metadata']['name']] = []
            for container in pod['status']['container_statuses']:
                choices[pod['metadata']['name']].append(container['name'])

        return choices

    @accepts(Str('release_name'))
    async def pod_console_choices(self, release_name):
        """
        Returns choices for console access to a chart release.

        Output is a dictionary with names of pods as keys and containing names of containers which the pod
        comprises of.
        """
        return await self.retrieve_pod_with_containers(release_name)

    @accepts()
    async def nic_choices(self):
        """
        Available choices for NIC which can be added to a pod in a chart release.
        """
        return await self.middleware.call('interface.choices')

    @accepts()
    async def used_ports(self):
        """
        Returns ports in use by applications.
        """
        return sorted(list(set({
            port['port']
            for chart_release in await self.middleware.call('chart.release.query')
            for port in chart_release['used_ports']
        })))

    @accepts()
    async def certificate_choices(self):
        """
        Returns certificates which can be used by applications.
        """
        return await self.middleware.call(
            'certificate.query', [['revoked', '=', False], ['cert_type_CSR', '=', False], ['parsed', '=', True]]
        )

    @accepts()
    async def certificate_authority_choices(self):
        """
        Returns certificate authorities which can be used by applications.
        """
        return await self.middleware.call(
            'certificateauthority.query', [['revoked', '=', False], ['parsed', '=', True]]
        )
