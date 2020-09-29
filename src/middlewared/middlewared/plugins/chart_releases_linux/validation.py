import copy
import itertools

from middlewared.service import private, Service
from middlewared.validators import validate_attributes

from .schema import get_schema


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def validate_values(self, item_version_details, data):
        default_values = item_version_details['values']
        new_values = copy.deepcopy(default_values)
        new_values.update(data['values'])

        verrors = validate_attributes(
            [get_schema(q) for q in item_version_details['questions']], {'values': new_values}
        )
        verrors.check()

        # If schema is okay, we see if we have question specific validation to be performed
        for question in item_version_details['questions']:
            await self.validate_question(verrors, question)

        verrors.check()

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
