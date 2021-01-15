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

    @accepts(Str('release_name'))
    async def retrieve_container_images(self, release_name):
        """
        Retrieve container images being used by a chart release.
        """
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        images_tags = list(set([
            c['image'] for pod in release['resources']['pods'] for c in pod['status']['container_statuses']
        ]))
        images = {}
        for image in await self.middleware.call('container.image.query'):
            for tag in images_tags:
                if tag in image['repo_tags']:
                    images[tag] = {**image, **(await self.middleware.call('container.image.parse_image_tag', tag))}

        return images
