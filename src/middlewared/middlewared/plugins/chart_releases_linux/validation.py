import itertools

from middlewared.schema import Dict
from middlewared.service import private, Service
from middlewared.validators import validate_attributes

from .utils import get_schema, update_conditional_validation


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def validate_values(self, item_version_details, new_values):
        attrs = list(itertools.chain.from_iterable(get_schema(q) for q in item_version_details['questions']))
        verrors = validate_attributes(
            attrs, {'values': new_values}, attr_key='values', dict_kwargs={
                'conditional_validation': update_conditional_validation(
                    Dict('attrs'), {'schema': {'attrs': item_version_details['questions']}}
                ).conditional_validation,
            }
        )
        verrors.check()

        # If schema is okay, we see if we have question specific validation to be performed
        for question in item_version_details['questions']:
            await self.validate_question(verrors, question)

        verrors.check()

        return attrs

    @private
    async def validate_question(self, verrors, question):
        schema = question['schema']
        for attr in itertools.chain(
            *[d.get(k, []) for d, k in zip((schema, schema, question), ('attrs', 'items', 'subquestions'))]
        ):
            await self.validate_question(verrors, attr)

        if not any(k.startswith('validations/') for k in schema.get('$ref', [])):
            return

        for validator_def in filter(lambda k: k.startswith('validations/'), schema['$ref']):
            pass
