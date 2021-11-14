from collections import defaultdict
from typing import Dict, List

from middlewared.service import CallError, private, Service

from .client import DockerClientMixin
from .utils import normalize_reference, DEFAULT_DOCKER_REGISTRY


class DockerImagesService(Service, DockerClientMixin):

    class Config:
        namespace = 'container.image'
        namespace_alias = 'docker.images'

    IMAGE_CACHE = defaultdict(lambda: False)

    @private
    async def image_update_cache(self):
        return self.IMAGE_CACHE

    @private
    def normalize_reference(self, reference: str) -> Dict:
        return normalize_reference(reference=reference)

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
    async def retrieve_image_digest(self, reference: str):
        repo_digest = None
        parsed_reference = self.normalize_reference(reference=reference)
        registry, image_str, tag_str = parsed_reference['registry'], parsed_reference['image'], parsed_reference['tag']
        if registry == DEFAULT_DOCKER_REGISTRY:
            repo_digest = await self._get_repo_digest(registry, image_str, tag_str)

        if not repo_digest:
            try:
                repo_digest = await self._get_latest_digest(registry, image_str, tag_str)
            except CallError as e:
                raise CallError(f'Failed to retrieve digest: {e}')

        return repo_digest

    @private
    async def parse_tags(self, references: List[str]) -> List[Dict[str, str]]:
        return [self.normalize_reference(reference=reference) for reference in references]

    @private
    async def check_update_for_image(self, tag, image_details):
        parsed_reference = self.normalize_reference(tag)
        self.IMAGE_CACHE[tag] = await self.compare_id_digests(
            image_details,
            parsed_reference['registry'],
            parsed_reference['image'],
            parsed_reference['tag']
        )

    @private
    async def clear_update_flag_for_tag(self, tag):
        self.IMAGE_CACHE[tag] = False

    @private
    async def compare_id_digests(self, image_details, registry, image_str, tag_str):
        """
        Returns whether an update is available for an image.
        """
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
