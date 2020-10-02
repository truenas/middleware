from collections import Callable

from middlewared.schema import Dict, List
from middlewared.service import private, Service, ValidationErrors


ref_mapping = {
    'normalise/interfaceConfiguration': 'interface_configuration'
}


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for method in ref_mapping.values():
            assert isinstance(getattr(self, f'normalise_{method}'), Callable) is True

    @private
    async def get_normalised_values(self, attrs, values, update=False):
        # TODO: Add proper subquestions support ensuring it's supported at all relevant places
        for attr in attrs:
            if not update and attr.name not in values and attr.default:
                values[attr.name] = attr.default
            if attr.name not in values:
                continue

            values[attr.name] = await self.normalise_question(attr, values[attr.name], update, values)

        return values

    @private
    async def normalise_question(self, question_attr, value, update, complete_config):
        schema = question_attr['schema']
        if isinstance(question_attr, Dict):
            for attr in question_attr.attrs.values():
                if not update and attr.name not in value and attr.default:
                    value[attr.name] = attr.default
                if attr.name not in value:
                    continue

                value[attr.name] = await self.normalise_question(attr, value[attr.name], update, complete_config)

        if isinstance(question_attr, List):
            for index, item in enumerate(value):
                for attr in question_attr.items:
                    try:
                        attr.validate(item)
                    except ValidationErrors:
                        pass
                    else:
                        value[index] = await self.normalise_question(attr, item, update, complete_config)
                        break

        for ref in filter(lambda k: k in ref_mapping, schema.get('$ref', [])):
            value = await self.middleware.call(
                f'chart.release.normalise_{ref_mapping[ref]}', question_attr, value, complete_config
            )

        return value

    @private
    async def normalise_interface_configuration(self, attr, value, complete_config):
        pass
