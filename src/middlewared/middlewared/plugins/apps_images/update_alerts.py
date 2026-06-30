from __future__ import annotations

from collections import defaultdict
import logging
from typing import TYPE_CHECKING

from middlewared.api.current import AppImageEntry, AppRegistryEntry
from middlewared.service import CallError

from .client import ContainerRegistryClientMixin
from .utils import get_normalized_auth_config, normalize_reference

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
    # Query stored Docker Registries once per cycle; per-tag credentials lookup
    # happens in `_check_update_for_image` via `get_normalized_auth_config`.
    registries = await context.call2(context.s.app.registry.query)
    for image in images:
        for tag in image.repo_tags:
            try:
                await _check_update_for_image(tag, image, registries)
            except CallError as e:
                logger.error(str(e))
            except Exception:
                # A single misbehaving image/registry must not abort the whole sweep
                # (and surface as an unretrieved task exception); log and move on.
                logger.error('Failed to check for image update for %r', tag, exc_info=True)


async def _check_update_for_image(
    tag: str,
    image: AppImageEntry,
    registries: list[AppRegistryEntry],
) -> None:
    if image.dangling:
        return

    parsed_reference = normalize_reference(tag)
    # Without per-registry auth the manifest call hits the public/anonymous code
    # path; for private repos (e.g. ghcr.io) that yields a token with no read
    # scope, the retry 401s, and no update is ever detected. When credentials
    # are configured we forward them as the aiohttp BasicAuth(**auth) kwargs
    # shape (`login` / `password`) the underlying client expects.
    auth: dict[str, str] | None = None
    if creds := get_normalized_auth_config(registries, tag):
        auth = {"login": creds["username"], "password": creds["password"]}
    IMAGE_CACHE[tag] = await _compare_id_digests(
        image,
        parsed_reference["registry"],
        parsed_reference["image"],
        parsed_reference["tag"],
        auth,
    )


async def _compare_id_digests(
    image: AppImageEntry,
    registry: str,
    image_str: str,
    tag_str: str,
    auth: dict[str, str] | None,
) -> bool:
    """Return whether an update is available for the image."""
    if not image.repo_digests:
        return False

    upstream_digests = await ContainerRegistryClientMixin()._get_repo_digest(
        registry, image_str, tag_str, auth=auth,
    )
    return not any(
        repo_digest.split("@", 1)[-1] == upstream_digest
        for upstream_digest in upstream_digests
        for repo_digest in image.repo_digests
    )
