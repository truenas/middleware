import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Str, returns
from middlewared.service import CRUDService, private, ValidationErrors

from .exporters.factory import export_factory


class ReportingExportsModel(sa.Model):
    __tablename__ = 'reporting_exporters'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean())
    type = sa.Column(sa.String())
    name = sa.Column(sa.String())
    attributes = sa.Column(sa.JSON())


class ReportingExportsService(CRUDService):

    class Config:
        namespace = 'reporting.exporters'
        datastore = 'reporting.exporters'
        cli_namespace = 'reporting.exporters'
        role_prefix = 'REPORTING'

    ENTRY = Dict(
        'reporting_exporter_entry',
        Int('id', required=True),
        Bool('enabled', required=True),
        Str(
            'type', enum=[authenticator for authenticator in export_factory.get_exporters()],
            required=True,
        ),
        Dict(
            'attributes',
            additional_attrs=True,
            description='Specific attributes of each `exporter`'
        ),
        Str('name', description='User defined name of exporter configuration', required=True),
    )

    def __init__(self, *args, **kwargs):
        super(ReportingExportsService, self).__init__(*args, **kwargs)
        self.exporters = self.get_exporter_schemas()

    @private
    async def common_validation(self, data, schema_name, old=None):
        verrors = ValidationErrors()
        filters = [['name', '!=', old['name']]] if old else []
        filters.append(['name', '=', data['name']])
        if await self.query(filters):
            verrors.add(f'{schema_name}.name', 'Specified name is already in use')

        if data['type'] not in self.exporters:
            verrors.add(
                f'{schema_name}.type',
                f'System does not support {data["type"]} as a reporting exporter type.'
            )
        else:
            exporter_obj = self.get_exporter_object(data)
            try:
                data['attributes'] = await exporter_obj.validate_config(data['attributes'])
            except ValidationErrors as ve:
                verrors.extend(ve)

        verrors.check()

    async def do_create(self, data):
        """
        Create a specific reporting exporter configuration containing required details for exporting reporting metrics.
        """
        await self.common_validation(data, 'reporting_exporter_create')

        oid = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
        )

        if data['enabled']:
            # Only restart if this is enabled
            await self.middleware.call('service.restart', 'netdata')

        return await self.get_instance(oid)

    @accepts(
        Int('id'),
        Patch(
            'reporting_exporter_entry',
            'reporting_exporter_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'type'}),
            ('attr', {'update': True}),
        ),
    )
    async def do_update(self, oid, data):
        """
        Update Reporting Exporter of `id`.
        """
        old = await self.get_instance(oid)
        new = old.copy()
        attrs = data.pop('attributes', {})
        new.update(data)
        new['attributes'].update(attrs)  # this is to be done separately so as to not overwrite the dict

        await self.common_validation(new, 'reporting_exporter_update', old)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            oid,
            new
        )

        await self.middleware.call('service.restart', 'netdata')

        return await self.get_instance(oid)

    async def do_delete(self, oid):
        """
        Delete Reporting Exporter of `id`.
        """
        await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            oid,
        )
        await self.middleware.call('service.restart', 'netdata')
        return True

    @accepts(roles=['REPORTING_READ'])
    @returns(List(
        title='Reporting Exporter Schemas',
        items=[Dict(
            'schema_entry',
            Str('key', required=True),
            List(
                'schema',
                items=[Dict(
                    'attribute_schema',
                    additional_attrs=True,
                    title='Attribute Schema',
                )],
            ),
            title='Reporting Exporter Schema'
        )],
    ))
    def exporter_schemas(self):
        """
        Get the schemas for all the reporting export types we support with their respective attributes
        required for successfully exporting reporting metrics to them.
        """
        return [
            {'schema': [v.to_json_schema() for v in value.attrs.values()], 'key': key}
            for key, value in self.exporters.items()
        ]

    @private
    def get_exporter_object(self, data):
        return export_factory.exporter(data['type'])()

    @private
    def get_exporter_schemas(self):
        return {k: klass.SCHEMA for k, klass in export_factory.get_exporters().items()}
