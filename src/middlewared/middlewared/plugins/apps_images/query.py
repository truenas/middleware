from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from middlewared.api.current import AppImageEntry, QueryOptions
from middlewared.plugins.apps.ix_apps.docker.images import list_images
from middlewared.plugins.apps.utils import to_entries
from middlewared.service import ServiceContext
from middlewared.service_exception import InstanceNotFound
from middlewared.utils.filter_list import filter_list

from .update_alerts import IMAGE_CACHE
from .utils import parse_tags

if TYPE_CHECKING:

    class _QueryGetOptions(QueryOptions):
        get: Literal[True]
        count: Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: Literal[True]
        get: Literal[False]


@overload
def query_images(  # type: ignore[overload-overlap]
    context: ServiceContext,
    filters: list[Any],
    options: _QueryCountOptions,
) -> int: ...


@overload
def query_images(  # type: ignore[overload-overlap]
    context: ServiceContext,
    filters: list[Any],
    options: _QueryGetOptions,
) -> AppImageEntry: ...


@overload
def query_images(
    context: ServiceContext,
    filters: list[Any],
    options: QueryOptions,
) -> list[AppImageEntry]: ...


def query_images(
    context: ServiceContext,
    filters: list[Any],
    options: QueryOptions,
) -> list[AppImageEntry] | AppImageEntry | int:
    if not context.call_sync2(context.s.docker.validate_state, False):
        return to_entries(filter_list([], filters, options.model_dump()), AppImageEntry)

    parse_all_tags = options.extra.get('parse_tags')
    images: list[dict[str, Any]] = []
    for image in list_images():
        repo_tags = image.get('repo_tags', [])
        config: dict[str, Any] = {
            'id': image.get('id'),
            'repo_tags': repo_tags,
            'repo_digests': image.get('repo_digests', []),
            'size': image.get('size'),
            'created': image.get('created'),
            'author': image.get('author'),
            'comment': image.get('comment'),
            'dangling': len(repo_tags) == 1 and repo_tags[0] == '<none>:<none>',
            'update_available': any(IMAGE_CACHE[r] for r in repo_tags),
        }
        if parse_all_tags:
            config['parsed_repo_tags'] = parse_tags(repo_tags)
        images.append(config)

    return to_entries(filter_list(images, filters, options.model_dump()), AppImageEntry)


def get_image_instance(
    context: ServiceContext,
    image_id: str,
    options: QueryOptions,
) -> AppImageEntry:
    results = query_images(context, [['id', '=', image_id]], QueryOptions(extra=options.extra))
    if not results:
        raise InstanceNotFound(f'Image {image_id} does not exist')
    return results[0]
