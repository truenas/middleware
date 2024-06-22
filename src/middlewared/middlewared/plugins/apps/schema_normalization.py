from collections.abc import Callable

from middlewared.schema import Cron, Dict, List
from middlewared.service import Service

from .schema_utils import get_list_item_from_value, RESERVED_NAMES


REF_MAPPING = {}


class AppSchemaService(Service):

    class Config:
        namespace = 'app.schema'
        private = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for method in REF_MAPPING.values():
            assert isinstance(getattr(self, f'normalize_{method}'), Callable) is True

    async def normalise_and_validate_values(self, item_details, values, update, app_dir, app_data=None):
        dict_obj = await self.middleware.call(
            'app.schema.validate_values', item_details, values, update, app_data,
        )
        return await self.normalize_values(dict_obj, values, update, {
            'app': {
                'name': app_dir.split('/')[-1],
                'path': app_dir,
            },
            'actions': [],
        })

    async def normalize_values(self, dict_obj, values, update, context):
        for k in RESERVED_NAMES:
            # We reset reserved names from configuration as these are automatically going to
            # be added by middleware during the process of normalising the values
            values[k[0]] = k[1]()

        for attr in filter(lambda v: v.name in values, dict_obj.attrs.values()):
            values[attr.name] = await self.normalize_question(attr, values[attr.name], update, values, context)

        return values, context

    async def normalize_question(self, question_attr, value, update, complete_config, context):
        if value is None and isinstance(question_attr, (Dict, List)):
            # This shows that the value provided has been explicitly specified as null and if validation
            # was okay with it, we shouldn't try to normalize it
            return value

        if isinstance(question_attr, Dict) and not isinstance(question_attr, Cron):
            for attr in filter(lambda v: v.name in value, question_attr.attrs.values()):
                value[attr.name] = await self.normalize_question(
                    attr, value[attr.name], update, complete_config, context
                )

        if isinstance(question_attr, List):
            for index, item in enumerate(value):
                _, attr = get_list_item_from_value(item, question_attr)
                if attr:
                    value[index] = await self.normalize_question(attr, item, update, complete_config, context)

        for ref in filter(lambda k: k in REF_MAPPING, question_attr.ref):
            value = await self.middleware.call(
                f'app.schema.normalize_{REF_MAPPING[ref]}', question_attr, value, complete_config, context
            )

        return value
