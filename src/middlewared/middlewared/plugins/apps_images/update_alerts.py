import contextlib

from collections import defaultdict

from middlewared.service import CallError, Service

from .client import ContainerRegistryClientMixin
from .utils import normalize_reference


class ContainerImagesService(Service, ContainerRegistryClientMixin):

    class Config:
        namespace = 'app.image'
        private = True

    IMAGE_CACHE = defaultdict(lambda: False)

    async def image_update_cache(self):
        return self.IMAGE_CACHE

    def normalize_reference(self, reference: str) -> dict:
        return normalize_reference(reference=reference)

    async def check_update(self):
        images = await self.middleware.call('container.image.query')
        for image in filter(lambda i: not i['system_image'], images):
            for tag in image['repo_tags']:
                try:
                    await self.check_update_for_image(tag, image)
                except CallError as e:
                    self.logger.error(str(e))

    async def retrieve_image_digest(self, reference: str):
        repo_digests = []
        parsed_reference = self.normalize_reference(reference=reference)
        with contextlib.suppress(CallError):
            repo_digests = await self._get_repo_digest(
                parsed_reference['registry'],
                parsed_reference['image'],
                parsed_reference['tag'],
            )

        return repo_digests

    async def check_update_for_image(self, tag, image_details):
        if not image_details['dangling']:
            parsed_reference = self.normalize_reference(tag)
            self.IMAGE_CACHE[tag] = await self.compare_id_digests(
                image_details,
                parsed_reference['registry'],
                parsed_reference['image'],
                parsed_reference['tag']
            )

    async def clear_update_flag_for_tag(self, tag):
        self.IMAGE_CACHE[tag] = False

    async def compare_id_digests(self, image_details, registry, image_str, tag_str):
        """
        Returns whether an update is available for an image.
        """
        digest = await self._get_repo_digest(registry, image_str, tag_str)
        return not any(
            digest.split('@', 1)[-1] == upstream_digest
            for upstream_digest in digest
            for digest in image_details['repo_digests']
        ) if image_details['repo_digests'] else False

    async def remove_image_from_cache(self, image):
        for tag in image['repo_tags']:
            self.IMAGE_CACHE.pop(tag, None)
