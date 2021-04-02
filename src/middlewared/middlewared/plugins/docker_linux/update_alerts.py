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
                    await self.check_update_for_image(tag, image)
                except CallError as e:
                    self.logger.error(str(e))

    @private
    async def retrieve_image_digest(self, tag):
        repo_digest = None
        parsed_tag = await self.parse_image_tag(tag)
        registry, image_str, tag_str = parsed_tag['registry'], parsed_tag['image'], parsed_tag['tag']
        if registry == DEFAULT_DOCKER_REGISTRY:
            repo_digest = await self._get_repo_digest(registry, image_str, tag_str)

        if not repo_digest:
            try:
                repo_digest = await self._get_latest_digest(registry, image_str, tag_str)
            except CallError as e:
                raise CallError(f'Failed to retrieve digest: {e}')

        return repo_digest

    @private
    async def parse_tags(self, tags):
        return [await self.parse_image_tag(tag) for tag in tags]

    @private
    async def parse_image_tag(self, tag):
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
        return {
            'image': image_str,
            'tag': tag_str,
            'registry': registry,
            'complete_tag': f'{registry}/{image_str}:{tag_str}',
        }

    @private
    async def check_update_for_image(self, tag, image_details):
        parsed_tag = await self.parse_image_tag(tag)
        if await self.compare_id_digests(image_details, parsed_tag['registry'], parsed_tag['image'], parsed_tag['tag']):
            self.IMAGE_CACHE[tag] = True
        else:
            await self.clear_update_flag_for_tag(tag)

    @private
    async def clear_update_flag_for_tag(self, tag):
        self.IMAGE_CACHE[tag] = False

    @private
    async def compare_id_digests(self, image_details, registry, image_str, tag_str):
        # Returns true if an update is available otherwise returns false
        repo_digest = None
        if registry == DEFAULT_DOCKER_REGISTRY:
            repo_digest = await self._get_repo_digest(registry, image_str, tag_str)
        if not repo_digest:
            try:
                digest = await self._get_latest_digest(registry, image_str, tag_str)
            except CallError as e:
                raise CallError(f'Failed to retrieve digest: {e}')

            return digest != image_details['id']
        else:
            return not any(digest.split('@', 1)[-1] == repo_digest for digest in image_details['repo_digests'])

    @private
    async def remove_image_from_cache(self, image):
        for tag in image['repo_tags']:
            self.IMAGE_CACHE.pop(tag, None)
