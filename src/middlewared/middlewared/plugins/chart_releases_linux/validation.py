import itertools

from middlewared.schema import Dict, NOT_PROVIDED
from middlewared.service import CallError, private, Service
from middlewared.utils import filter_list
from middlewared.validators import validate_attributes

from .schema import get_schema, get_list_item_from_value, update_conditional_defaults
from .utils import RESERVED_NAMES


validation_mapping = {
    'definitions/certificate': 'certificate',
    'definitions/certificateAuthority': 'certificate_authority',
    'validations/containerImage': 'container_image',
    'validations/nodePort': 'port_available_on_node',
}


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def construct_schema_for_item_version(
        self, item_version_details, new_values, update, old_values=NOT_PROVIDED
    ):
        schema_name = f'chart_release_{"update" if update else "create"}'
        attrs = list(itertools.chain.from_iterable(
            get_schema(q, update, old_values) for q in item_version_details['schema']['questions']
        ))
        dict_obj = update_conditional_defaults(
            Dict(schema_name, *attrs, update=update, additional_attrs=True), {
                'schema': {'attrs': item_version_details['schema']['questions']}
            }
        )

        verrors = validate_attributes(
            attrs, {'values': new_values}, True, attr_key='values', dict_kwargs={
                'conditional_defaults': dict_obj.conditional_defaults, 'update': update,
            }
        )
        return {
            'verrors': verrors,
            'new_values': new_values,
            'dict_obj': dict_obj,
            'schema_name': schema_name,
        }

    @private
    async def validate_values(self, item_version_details, new_values, update, release_data=None):
        for k in RESERVED_NAMES:
            new_values.pop(k[0], None)

        verrors, new_values, dict_obj, schema_name = (
            await self.construct_schema_for_item_version(
                item_version_details, new_values, update, (release_data or {}).get('config', NOT_PROVIDED)
            )
        ).values()

        verrors.check()

        # If schema is okay, we see if we have question specific validation to be performed
        questions = {}
        for variable in item_version_details['schema']['questions']:
            questions[variable['variable']] = variable
            if 'subquestions' in variable.get('schema', {}):
                for sub_variable in variable['schema']['subquestions']:
                    questions[sub_variable['variable']] = sub_variable
        for key in filter(lambda k: k in questions, new_values):
            await self.validate_question(
                verrors, new_values[key], questions[key], dict_obj.attrs[key], schema_name, release_data,
            )

        verrors.check()

        return dict_obj

    @private
    async def validate_question(self, verrors, value, question, var_attr, schema_name, release_data=None):
        schema = question['schema']
        schema_name = f'{schema_name}.{question["variable"]}'

        # TODO: Add nested support for subquestions
        if schema['type'] == 'dict' and value:
            dict_attrs = {v['variable']: v for v in schema['attrs']}
            for k in filter(lambda k: k in dict_attrs, value):
                await self.validate_question(
                    verrors, value[k], dict_attrs[k], var_attr.attrs[k], f'{schema_name}.{k}', release_data,
                )

        elif schema['type'] == 'list' and value:
            for index, item in enumerate(value):
                item_index, attr = get_list_item_from_value(item, var_attr)
                if attr:
                    await self.validate_question(
                        verrors, item, schema['items'][item_index], attr, f'{schema_name}.{index}', release_data,
                    )

        for validator_def in filter(lambda k: k in validation_mapping, schema.get('$ref', [])):
            await self.middleware.call(
                f'chart.release.validate_{validation_mapping[validator_def]}', verrors, value, question, schema_name,
                release_data,
            )

        return verrors

    @private
    async def validate_port_available_on_node(self, verrors, value, question, schema_name, release_data):
        if release_data and value in [p['port'] for p in release_data['used_ports']]:
            # TODO: This still leaves a case where user has multiple ports in a single app and mixes
            #  them to the same value however in this case we will still get an error raised by k8s.
            return

        if value in await self.middleware.call('chart.release.used_ports'):
            verrors.add(schema_name, 'Port is already in use.')

    @private
    async def validate_certificate(self, verrors, value, question, schema_name, release_data):
        if not value:
            return

        if not filter_list(await self.middleware.call('chart.release.certificate_choices'), [['id', '=', value]]):
            verrors.add(schema_name, 'Unable to locate certificate.')

    @private
    async def validate_certificate_authority(self, verrors, value, question, schema_name, release_data):
        if not value:
            return

        if not filter_list(
            await self.middleware.call('chart.release.certificate_authority_choices'), [['id', '=', value]]
        ):
            verrors.add(schema_name, 'Unable to locate certificate authority.')

    @private
    async def validate_container_image(self, verrors, value, question, schema_name, release_data):
        # We allow chart devs to bypass container image validation in case we have a case where a registry misbehaves
        # or maybe there is an issue in our code to correctly see if container image exists.
        if not value or not value.get('validate', True):
            return

        # If validation is to be performed now, we expect that we at least have repo + tag available always
        for k in filter(lambda k: not value.get(k), ('repository', 'tag')):
            verrors.add(schema_name, f'{k!r} must be specified.')

        tag = f'{value["repository"]}:{value["tag"]}'
        try:
            digest = await self.middleware.call('container.image.retrieve_image_digest', tag)
        except CallError as e:
            verrors.add(schema_name, f'Failed to validate {tag!r} image tag ({e})')
        else:
            if not digest:
                verrors.add(schema_name, f'Unable to retrieve {tag!r} container image tag details.')
