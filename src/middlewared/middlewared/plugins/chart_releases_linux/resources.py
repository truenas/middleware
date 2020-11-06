from middlewared.schema import Str
from middlewared.service import accepts, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(Str('release_name'))
    async def pod_console_choices(self, release_name):
        """
        Returns choices for console access to a chart release.

        Output is a dictionary with names of pods as keys and containing names of containers which the pod
        comprises of.
        """
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        choices = {}
        for pod in release['resources']['pods']:
            choices[pod['metadata']['name']] = []
            for container in pod['status']['container_statuses']:
                choices[pod['metadata']['name']].append(container['name'])

        return choices
