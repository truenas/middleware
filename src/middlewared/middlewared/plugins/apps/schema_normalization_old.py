import os
from collections.abc import Callable

from middlewared.service import Service

from .ix_apps.path import get_app_volume_path
from .schema_action_context import apply_acls, update_volumes
from .schema_construction_utils import RESERVED_NAMES

REF_MAPPING = {
    'definitions/certificate',
    'definitions/gpu_configuration',
    'normalize/acl',
    'normalize/ix_volume',
}


class AppSchemaService(Service):

    class Config:
        namespace = 'app.schema'
        private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for method in REF_MAPPING.values():
            assert isinstance(getattr(self, f'normalize_{method}'), Callable) is True

        self.kfd_exists = os.path.exists('/dev/kfd')

    async def normalize_and_validate_values(
        self, item_details, values, update, app_dir, app_data=None, perform_actions=True,
    ):
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


