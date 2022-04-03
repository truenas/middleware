from middlewared.schema import List, returns, Str
from middlewared.service import accepts, Service

from .utils import get_chart_releases_consuming_image


class DockerImagesService(Service):

    class Config:
        namespace = 'container.image'
        namespace_alias = 'docker.images'
        cli_namespace = 'app.docker.image'

    @accepts(List('image_tags', empty=False, items=[Str('image_tag')]))
    @returns(List())
    async def get_chart_releases_consuming_image(self, image_tags):
        """
        Retrieve chart releases consuming `image_tag` image.
        """
        return get_chart_releases_consuming_image(
            image_tags, await self.middleware.call('chart.release.query', [], {'extra': {'retrieve_resources': True}})
        )
