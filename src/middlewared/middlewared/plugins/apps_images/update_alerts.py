from __future__ import annotations

from collections import defaultdict
import logging
from typing import TYPE_CHECKING

from middlewared.api.current import AppImageEntry
from middlewared.service import CallError

from .client import ContainerRegistryClientMixin
from .utils import normalize_reference

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


logger = logging.getLogger("docker_image")


# Module-level cache mapping repo_tag -> "update available?" boolean.
# Populated by `check_update_impl`, cleared per-tag by `clear_update_flag_impl` /
# `remove_from_cache`, read by `get_update_cache_impl`.
IMAGE_CACHE: defaultdict[str, bool] = defaultdict(lambda: False)


async def get_update_cache_impl(normalized: bool = False) -> dict[str, bool]:
    if normalized:
        return {normalize_reference(i)["complete_tag"]: v for i, v in IMAGE_CACHE.items()}
    return dict(IMAGE_CACHE)


async def clear_update_flag_impl(tag: str) -> None:
    IMAGE_CACHE[tag] = False


def remove_from_cache(image: AppImageEntry) -> None:
    for tag in image.repo_tags:
        IMAGE_CACHE.pop(tag, None)


async def check_update_impl(context: ServiceContext) -> None:
    images = await context.call2(context.s.app.image.query)
    for image in images:
        for tag in image.repo_tags:
            try:
                await _check_update_for_image(tag, image)
            except CallError as e:
                logger.error(str(e))


async def _check_update_for_image(tag: str, image: AppImageEntry) -> None:
    if image.dangling:
        return

    parsed_reference = normalize_reference(tag)
    IMAGE_CACHE[tag] = await _compare_id_digests(
        image,
        parsed_reference["registry"],
        parsed_reference["image"],
        parsed_reference["tag"],
    )


async def _compare_id_digests(
    image: AppImageEntry,
    registry: str,
    image_str: str,
    tag_str: str,
) -> bool:
    """Return whether an update is available for the image."""
    if not image.repo_digests:
        return False

    upstream_digests = await ContainerRegistryClientMixin()._get_repo_digest(registry, image_str, tag_str)
    return not any(
        repo_digest.split("@", 1)[-1] == upstream_digest
        for upstream_digest in upstream_digests
        for repo_digest in image.repo_digests
    )
