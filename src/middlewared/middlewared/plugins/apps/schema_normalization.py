from __future__ import annotations

import functools
import os
import typing
from collections.abc import Callable

from middlewared.service import ServiceContext

from .ix_apps.path import get_app_volume_path
from .schema_action_context import apply_acls, update_volumes
from .schema_construction_utils import RESERVED_NAMES


async def normalize_and_validate_values(
    context: ServiceContext, item_details, values, update, app_dir, app_data=None, perform_actions=True,
) -> dict[str, typing.Any]:
    new_values = await self.middleware.call('app.schema.validate_values', item_details, values, update, app_data)
    new_values, context = await self.normalize_values(item_details['schema']['questions'], new_values, update, {
        'app': {
            'name': app_dir.split('/')[-1],
            'path': app_dir,
        },
        'actions': [],
    })
    if perform_actions:
        await self.perform_actions(context)
    return new_values


@functools.cache
def kfd_exists() -> bool:
    return os.path.exists('/dev/kfd')
