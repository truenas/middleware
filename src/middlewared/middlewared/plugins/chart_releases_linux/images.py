import errno

from middlewared.plugins.docker_linux.utils import normalize_reference, get_chart_releases_consuming_image
from middlewared.schema import Dict, Str, returns
from middlewared.service import accepts, CallError, private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(Str('chart_release_name'))
    @returns(Dict(example={'minio2': ['minio/minio:RELEASE.2022-03-05T06-32-39Z']}))
    async def get_chart_releases_using_chart_release_images(self, chart_release_name):
        """
        Retrieve chart releases which are consuming any images in use by `chart_release_name`.
        """
        chart_releases = await self.middleware.call('chart.release.query', [], {'extra': {'retrieve_resources': True}})
        idx = next((idx for (idx, d) in enumerate(chart_releases) if d['name'] == chart_release_name), None)
        if idx is None:
            raise CallError(f'{chart_release_name!r} not found', errno=errno.ENOENT)

        chart_release = chart_releases.pop(idx)
        return get_chart_releases_consuming_image(chart_release['resources']['container_images'], chart_releases, True)

    @private
    async def delete_unused_app_images(self, chart_release):
        failed_to_delete = {}
        to_delete_tags = await self.get_to_delete_unused_app_images(chart_release)
        for image in await self.middleware.call('container.image.query', [['OR', [
            ['complete_tags', 'rin', tag] for tag in to_delete_tags
        ]]], {'extra': {'complete_tags': True}}) if to_delete_tags else []:
            try:
                await self.middleware.call('container.image.delete', image['id'])
            except Exception as e:
                failed_to_delete[', '.join(image['complete_tags'])] = str(e)
        return failed_to_delete

    @private
    async def get_to_delete_unused_app_images(self, chart_release):
        to_delete = {normalize_reference(i)['complete_tag'] for i in chart_release['resources']['container_images']}
        in_use = get_chart_releases_consuming_image(
            to_delete, await self.middleware.call(
                'chart.release.query', [['id', '!=', chart_release['name']]], {'extra': {'retrieve_resources': True}}
            ), True
        )
        for image_list in in_use.values():
            for image in filter(lambda i: i['complete_tag'] in to_delete, map(normalize_reference, image_list)):
                to_delete.remove(image['complete_tag'])
        return list(to_delete)
