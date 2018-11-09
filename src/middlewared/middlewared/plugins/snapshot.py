from middlewared.schema import accepts, Bool, Cron, Dict, Int, List, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.validators import ReplicationSnapshotNamingSchema


class PeriodicSnapshotTaskService(CRUDService):

    class Config:
        datastore = 'storage.task'
        datastore_prefix = 'task_'
        datastore_extend = 'pool.snapshottask.extend'
        namespace = 'pool.snapshottask'

    @private
    def extend(self, data):
        Cron.convert_db_format_to_schedule(data, begin_end=True)

        has_legacy_obstacles = bool(self._validate_legacy(data))
        data['legacy_allowed'] = not has_legacy_obstacles

        return data

    @accepts(
        Dict(
            'periodic_snapshot_create',
            Str('dataset', required=True),
            Bool('recursive', required=True),
            List('exclude', items=[Str('item', empty=False)], default=[]),
            Int('lifetime_value', required=True),
            Str('lifetime_unit', enum=['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'], required=True),
            Str('naming_schema', required=True, validators=[ReplicationSnapshotNamingSchema()]),
            Cron('schedule', required=True, begin_end=True),
            Bool('enabled', default=True),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()

        await self._validate(verrors, 'periodic_snapshot_create', data)

        if verrors:
            raise verrors

        Cron.convert_schedule_to_db_format(data, begin_end=True)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.restart', 'cron')

        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch('periodic_snapshot_create', 'periodic_snapshot_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        await self._validate(verrors, 'periodic_snapshot_create', new)

        legacy_replication_tasks = await self.middleware.call(
            'datastore.query',
            'storage.replication',
            [
                ['tasks__id', '=', new['id']],
                ['transport', '=', 'LEGACY'],
            ],
            {'prefix': 'repl_'}
        )
        if legacy_replication_tasks:
            verrors.add_child(f'periodic_snapshot_update', self._validate_legacy(new))

        if verrors:
            raise verrors

        Cron.convert_schedule_to_db_format(data, begin_end=True)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.restart', 'cron')

        return await self._get_instance(id)

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call('service.restart', 'cron')

        return response

    async def _validate(self, verrors, schema_name, data):
        if data['dataset'] not in (await self.middleware.call('pool.filesystem_choices')):
            verrors.add(
                f'{schema_name}.dataset',
                'Invalid ZFS dataset'
            )

        if not data['recursive'] and data['exclude']:
            verrors.add(
                f'{schema_name}.exclude',
                'Excluding datasets has no sense for non-recursive periodic snapshot tasks'
            )

        for i, v in enumerate(data['exclude']):
            if not v.startswith(f'{data["dataset"]}/'):
                verrors.add(
                    f'{schema_name}.exclude.{i}',
                    'Excluded dataset should be a child of selected dataset'
                )

    def _validate_legacy(self, data):
        verrors = ValidationErrors()

        if data['exclude']:
            verrors.add(
                'exclude',
                ('Excluding child datasets is not available because this snapshot task is being used in '
                 'legacy replication task. Please upgrade your replication tasks to edit this field.'),
            )

        naming_schema = f'auto-%Y%m%d.%H%M%S-{data["lifetime_value"]}{data["lifetime_unit"].lower()[0]}'
        if data['naming_schema'] != naming_schema:
            verrors.add(
                'naming_schema',
                (f'Naming schema should be {naming_schema} because this snapshot task is being used in legacy '
                 f'replication task. Please upgrade your replication tasks to edit this field.'),
            )

        return verrors
