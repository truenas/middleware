from collections import defaultdict

from middlewared.service import CallError, private, Service

from .client import DockerClientMixin
from .utils import DEFAULT_DOCKER_REGISTRY, DEFAULT_DOCKER_REPO, DEFAULT_DOCKER_TAG


class DockerImagesService(Service, DockerClientMixin):

    class Config:
        namespace = 'container.image'
        namespace_alias = 'docker.images'

    IMAGE_CACHE = defaultdict(lambda: False)

    @private
    async def image_update_cache(self):
        return self.IMAGE_CACHE

    @private
    async def check_update(self):
        images = await self.middleware.call('container.image.query')
        for image in filter(lambda i: not i['system_image'], images):
            for tag in image['repo_tags']:
                try:
                    await self.get_digest_of_image(tag, image)
                except CallError as e:
                    self.logger.error(str(e))

    @private
    async def get_digest_of_image(self, tag, image_details=None):
        # Following logic has been used from docker engine to make sure we follow the same rules/practices
        # for normalising the image name / tag
        i = tag.find('/')
        if i == -1 or (not any(c in tag[:i] for c in ('.', ':')) and tag[:i] != 'localhost'):
            registry, image_tag = DEFAULT_DOCKER_REGISTRY, tag
        else:
            registry, image_tag = tag[:i], tag[i + 1:]

        if '/' not in image_tag:
            image_tag = f'{DEFAULT_DOCKER_REPO}/{image_tag}'

        if ':' not in image_tag:
            image_tag += f':{DEFAULT_DOCKER_TAG}'

        image_str, tag_str = image_tag.rsplit(':', 1)

        try:
            digest = await self._get_latest_digest(registry, image_str, tag_str)
        except CallError as e:
            raise CallError(f'Failed to retrieve digest: {e}')
        else:
            if image_details:
                if digest != image_details['id']:
                    self.IMAGE_CACHE[tag] = True
                    await self.middleware.call(
                        'alert.oneshot_create', 'DockerImageUpdate', {'tag': tag, 'id': tag}
                    )
                else:
                    self.IMAGE_CACHE[tag] = False
                    await self.middleware.call('alert.oneshot_delete', 'DockerImageUpdate', tag)

            return digest

    @private
    async def remove_image_from_cache(self, image):
        for tag in image['repo_tags']:
            self.IMAGE_CACHE.pop(tag, None)
            await self.middleware.call('alert.oneshot_delete', 'DockerImageUpdate', tag)
