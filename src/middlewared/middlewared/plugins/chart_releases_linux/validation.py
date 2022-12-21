from pathlib import Path

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name
from middlewared.schema import Dict, NOT_PROVIDED
from middlewared.service import CallError, private, Service
from middlewared.utils import filter_list

from .schema import construct_schema, get_list_item_from_value
from .utils import CONTEXT_KEY_NAME, RESERVED_NAMES


validation_mapping = {
    'definitions/certificate': 'certificate',
    'definitions/certificateAuthority': 'certificate_authority',
    'validations/containerImage': 'container_image',
    'validations/nodePort': 'port_available_on_node',
    'validations/hostPath': 'custom_host_path',
    'normalize/ixVolume': 'ix_mount_path',
    'validations/lockedHostPath': 'locked_host_path',
    'validations/hostPathAttachments': 'host_path_attachments',
}


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def construct_schema_for_item_version(
        self, item_version_details, new_values, update, old_values=NOT_PROVIDED
    ):
        return construct_schema(item_version_details, new_values, update, old_values)

    @private
    async def validate_values(self, item_version_details, new_values, update, release_data=None):
        for k in RESERVED_NAMES:
            new_values.pop(k[0], None)

        # global key is special as in that it is shared with dependencies/subcharts which means that
        # it is entirely possible that it is already being specified by chart dev to specify some global
        # values for the chart(s) and in this case we just want to remove what global chart context we added
        if isinstance(new_values.get('global'), dict):
            new_values['global'].pop(CONTEXT_KEY_NAME, None)

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
        for key in filter(lambda k: k in questions, new_values):
            await self.validate_question(
                verrors=verrors,
                parent_value=new_values,
                value=new_values[key],
                question=questions[key],
                parent_attr=dict_obj,
                var_attr=dict_obj.attrs[key],
                schema_name=f'{schema_name}.{questions[key]["variable"]}',
                release_data=release_data,
            )

        verrors.check()

        return dict_obj

    @private
    async def validate_question(
        self, verrors, parent_value, value, question, parent_attr, var_attr, schema_name, release_data=None
    ):
        schema = question['schema']

        if schema['type'] == 'dict' and value:
            dict_attrs = {v['variable']: v for v in schema['attrs']}
            for k in filter(lambda k: k in dict_attrs, value):
                await self.validate_question(
                    verrors, value, value[k], dict_attrs[k],
                    var_attr, var_attr.attrs[k], f'{schema_name}.{k}', release_data,
                )

        elif schema['type'] == 'list' and value:
            for index, item in enumerate(value):
                item_index, attr = get_list_item_from_value(item, var_attr)
                if attr:
                    await self.validate_question(
                        verrors, value, item, schema['items'][item_index],
                        var_attr, attr, f'{schema_name}.{index}', release_data,
                    )

        if schema['type'] == 'hostpath':
            await self.validate_host_path_field(value, verrors, schema_name)

        for validator_def in filter(lambda k: k in validation_mapping, schema.get('$ref', [])):
            await self.middleware.call(
                f'chart.release.validate_{validation_mapping[validator_def]}',
                verrors, value, question, schema_name, release_data,
            )

        subquestions_enabled = (
            schema['show_subquestions_if'] == value
            if 'show_subquestions_if' in schema
            else 'subquestions' in schema
        )
        if subquestions_enabled:
            for sub_question in schema.get('subquestions', []):
                # TODO: Add support for nested subquestions validation for List schema types.
                if isinstance(parent_attr, Dict) and sub_question['variable'] in parent_value:
                    item_key, attr = sub_question['variable'], parent_attr.attrs[sub_question['variable']]
                    await self.validate_question(
                        verrors, parent_value, parent_value[sub_question['variable']], sub_question,
                        parent_attr, attr, f'{schema_name}.{item_key}', release_data,
                    )

        return verrors

    @private
    async def validate_host_path_field(self, value, verrors, schema_name):
        if not (await self.middleware.call('kubernetes.config'))['validate_host_path']:
            return

        if err_str := await self.middleware.call('chart.release.validate_host_source_path', value):
            verrors.add(schema_name, err_str)

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

    @private
    async def validate_custom_host_path(self, verrors, path, question, schema_name, release_data):
        if not path:
            return

        await self.validate_locked_host_path(verrors, path, question, schema_name, release_data)
        await self.validate_host_path_attachments(verrors, path, question, schema_name, release_data)
        await check_path_resides_within_volume(verrors, self.middleware, schema_name, path)

    @private
    async def validate_ix_mount_path(self, verrors, value, question, schema_name, release_data):
        path = value.get('datasetName') if isinstance(value, dict) else value
        if not path:
            verrors.add(schema_name, 'Dataset name should not be empty.')
        elif not validate_dataset_name(path):
            verrors.add(schema_name, f'Invalid dataset name {path}. "test1, ix-test, ix_test" are valid examples.')

    @private
    async def validate_locked_host_path(self, verrors, path, question, schema_name, release_data):
        if not path:
            return

        p = Path(path)
        if not p.is_absolute():
            verrors.add(schema_name, f'Must be an absolute path: {path}.')

        if await self.middleware.call('pool.dataset.path_in_locked_datasets', path):
            verrors.add(schema_name, f'Dataset is locked at path: {path}.')

    @private
    async def validate_host_path_attachments(self, verrors, path, question, schema_name, release_data):
        if not path:
            return

        p = Path(path)
        if not p.is_absolute():
            verrors.add(schema_name, f'Must be an absolute path: {path}.')

        if attachments := {
            attachment['type']
            for attachment in await self.middleware.call('pool.dataset.attachments_with_path', path)
            if attachment['type'].lower() not in ['kubernetes', 'chart releases']
        }:
            verrors.add(schema_name, f"The path '{path}' is already attached to service(s): {', '.join(attachments)}.")
