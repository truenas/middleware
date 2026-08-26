from pathlib import Path

from middlewared.service import Service
from middlewared.utils.filter_list import filter_list

from .ix_apps.path import is_app_mounts_path
from .schema_construction_utils import construct_schema, NOT_PROVIDED, RESERVED_NAMES


VALIDATION_REF_MAPPING = {
    'definitions/certificate': 'certificate',
    'definitions/port': 'port_available_on_node',
    'normalize/acl': 'acl_entries',
}
# FIXME: See which are no longer valid
# https://github.com/truenas/middleware/blob/249ed505a121e5238e225a89d3a1fa60f2e55d27/src/middlewared/middlewared/
# plugins/chart_releases_linux/validation.py#L13


class AppSchemaService(Service):

    class Config:
        namespace = 'app.schema'
        private = True

    async def validate_values(self, app_version_details, new_values, update, app_data=None):
        for k in RESERVED_NAMES:
            new_values.pop(k[0], None)

        verrors, new_values, schema_name = (
            construct_schema(
                app_version_details, new_values, update, (app_data or {}).get('config', NOT_PROVIDED)
            )
        ).values()

        verrors.check()

        # If schema is okay, we see if we have question specific validation to be performed
        questions = {}
        for variable in app_version_details['schema']['questions']:
            questions[variable['variable']] = variable
        for key in filter(lambda k: k in questions, new_values):
            await self.validate_question(
                verrors=verrors,
                value=new_values[key],
                question=questions[key],
                schema_name=f'{schema_name}.{questions[key]["variable"]}',
                app_data=app_data,
            )

        verrors.check()

        return new_values

    async def validate_question(
        self, verrors, value, question, schema_name, app_data=None
    ):
        schema = question['schema']

        if schema['type'] == 'dict' and schema.get('attrs') and value:
            dict_attrs = {v['variable']: v for v in schema['attrs']}
            for k in filter(lambda k: k in dict_attrs, value):
                await self.validate_question(
                    verrors, value[k], dict_attrs[k], f'{schema_name}.{k}', app_data,
                )

        elif schema['type'] == 'list' and value:
            for index, item in enumerate(value):
                if schema['items']:
                    await self.validate_question(
                        verrors, item, schema['items'][0],  # We will always have a single item schema
                        f'{schema_name}.{index}', app_data,
                    )

        # FIXME: See if this is valid or not and port appropriately
        """
        if schema['type'] == 'hostpath':
            await self.validate_host_path_field(value, verrors, schema_name)
        """
        for validator_def in filter(lambda k: k in VALIDATION_REF_MAPPING, schema.get('$ref', [])):
            await self.middleware.call(
                f'app.schema.validate_{VALIDATION_REF_MAPPING[validator_def]}',
                verrors, value, question, schema_name, app_data,
            )

        return verrors

    async def validate_certificate(self, verrors, value, question, schema_name, app_data):
        if not value:
            return

        if not filter_list(await self.middleware.call('app.certificate_choices'), [['id', '=', value]]):
            verrors.add(schema_name, 'Unable to locate certificate.')
            return

        sub_verrors = await self.middleware.call(
            'certificate.cert_services_validation', value, schema_name, False,
        )
        if sub_verrors:
            verrors.extend(sub_verrors)

    def validate_acl_entries(self, verrors, value, question, schema_name, app_data):
        path = value.get('path')
        if not path or value.get('options', {}).get('force'):
            return

        if is_app_mounts_path(path):
            # Everything under the app mounts directory is created and owned by middleware, so whether it holds
            # data is not middleware's call to refuse a save over - a stored `force: false` on an ix volume would
            # otherwise make the config permanently unsavable once the app has written anything into its volume.
            # Skipping only drops the pre-flight message: filesystem.add_to_acl still refuses an unforced apply
            # over a populated path, and `force` is written in exactly one place - normalize_ix_volume - which
            # only ever sets it for the requesting app's own volume.
            return

        try:
            if next(Path(path).iterdir(), None):
                verrors.add(schema_name, f'{path}: path contains existing data and `force` was not specified')
        except FileNotFoundError:
            verrors.add(schema_name, f'{path}: path does not exist')

    async def validate_port_available_on_node(self, verrors, value, question, schema_name, app_data):
        for port_entry in (app_data['active_workloads']['used_ports'] if app_data else []):
            for host_port in port_entry['host_ports']:
                if value == host_port['host_port']:
                    # TODO: This still leaves a case where user has multiple ports in a single app and mixes
                    #  them to the same value however in this case we will still get an error raised by docker.
                    return

        if value in await self.middleware.call('app.used_ports') or value in await self.middleware.call(
            'port.ports_mapping', 'app'
        ):
            verrors.add(schema_name, 'Port is already in use.')
