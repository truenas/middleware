from __future__ import annotations

from typing import Literal

from middlewared.api.current import AppImageDeleteOptions, QueryOptions
from middlewared.plugins.apps.ix_apps.docker.images import delete_image
from middlewared.service import ServiceContext

from .query import get_image_instance
from .update_alerts import remove_from_cache


def delete_image_action(
    context: ServiceContext, image_id: str, options: AppImageDeleteOptions,
) -> Literal[True]:
    context.call_sync2(context.s.docker.validate_state)
    image = get_image_instance(context, image_id, QueryOptions())
    delete_image(image_id, options.force)
    remove_from_cache(image)
    return True
