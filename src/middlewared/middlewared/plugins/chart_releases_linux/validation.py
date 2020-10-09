import itertools

from middlewared.schema import Dict
from middlewared.service import private, Service
from middlewared.validators import validate_attributes

from .utils import get_schema, get_list_item_from_value, update_conditional_validation, RESERVED_NAMES


validation_mapping = {
    'validations/persistentVolumeClaims': 'persistent_volume_claims',
}


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def validate_values(self, item_version_details, new_values, update):
        for k in RESERVED_NAMES:
            new_values.pop(k[0], None)

        schema_name = f'chart_release_{"update" if update else "create"}'
        attrs = list(itertools.chain.from_iterable(get_schema(q) for q in item_version_details['questions']))
        dict_obj = update_conditional_validation(
            Dict(schema_name, *attrs, update=update), {'schema': {'attrs': item_version_details['questions']}}
        )

        verrors = validate_attributes(
            attrs, {'values': new_values}, attr_key='values', dict_kwargs={
                'conditional_validation': dict_obj.conditional_validation, 'update': update,
            }
        )
        verrors.check()

        # If schema is okay, we see if we have question specific validation to be performed
        questions = item_version_details['questions']
        for key in new_values:
            await self.validate_question(verrors, new_values[key], questions[key], dict_obj.attrs[key], schema_name)

        verrors.check()

        return dict_obj

    @private
    async def validate_question(self, verrors, value, question, var_attr, schema_name):
        schema = question['schema']
        schema_name = f'{schema_name}.{question["variable"]}'

        # TODO: Add nested support for subquestions
        if schema['type'] == 'dict':
            dict_attrs = {v['variable']: v for v in schema['attrs']}
            for k in filter(lambda k: k in dict_attrs, value):
                await self.validate_question(
                    verrors, value[k], dict_attrs[k], var_attr.attrs[k], f'{schema_name}.{k}',
                )

        elif schema['type'] == 'list':
            for index, item in enumerate(value):
                item_index, attr = get_list_item_from_value(item, var_attr)
                if attr:
                    await self.validate_question(
                        verrors, item, schema['items'][item_index], attr, f'{schema_name}.{index}'
                    )

        for validator_def in filter(lambda k: k in validation_mapping, schema.get('$ref', [])):
            await self.middleware.call(
                f'chart.release.validate_{validation_mapping[validator_def]}', verrors, value, question, schema_name,
            )

        return verrors

    @private
    async def validate_persistent_volume_claims(self, verrors, value, question, schema_name):
        used_names = set()
        for index, pvc in enumerate(value):
            if pvc['name'] in used_names:
                verrors.add(f'{schema_name}.{index}.name', 'Names for PVC\'s must be unique')
