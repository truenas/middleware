from middlewared.schema import accepts, Bool, Cron, Dict, Int, List, Patch, Path, Str
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.utils.path import is_child
from middlewared.validators import ReplicationSnapshotNamingSchema


class PeriodicSnapshotTaskService(CRUDService):

    class Config:
        datastore = 'storage.task'
        datastore_prefix = 'task_'
        datastore_extend = 'pool.snapshottask.extend'
        datastore_extend_context = 'pool.snapshottask.extend_context'
        namespace = 'pool.snapshottask'

    @private
    async def extend_context(self):
        return {
            'legacy_replication_tasks': await self._legacy_replication_tasks(),
            'vmware': await self.middleware.call('vmware.query'),
        }

    @private
    async def extend(self, data, context):
        Cron.convert_db_format_to_schedule(data, begin_end=True)

        data['legacy'] = self._is_legacy(data, context['legacy_replication_tasks'])

        data['vmware_sync'] = any(
            (
                vmware['filesystem'] == data['dataset'] or
                (data['recursive'] and is_child(vmware['filesystem'], data['dataset']))
            )
            for vmware in context['vmware']
        )

        return data

    @accepts(
        Dict(
            'periodic_snapshot_create',
            Path('dataset', required=True),
            Bool('recursive', required=True),
            List('exclude', items=[Path('item', empty=False)], default=[]),
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

        verrors.add_child('periodic_snapshot_create', await self._validate(data))

        if verrors:
            raise verrors

        if self._is_legacy(data, await self._legacy_replication_tasks()):
            verrors.add_child('periodic_snapshot_create', self._validate_legacy(data))

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

        verrors.add_child('periodic_snapshot_update', await self._validate(new))

        if not data['enabled']:
            for replication_task in await self.middleware.call('replication.query', [['enabled', '=', True]]):
                if any(periodic_snapshot_task['id'] == id
                       for periodic_snapshot_task in replication_task['periodic_snapshot_tasks']):
                    verrors.add(
                        'periodic_snapshot_update.enabled',
                        (f'You can\'t disable this periodic snapshot task because it is bound to enabled replication '
                         f'task {replication_task["id"]!r}')
                    )
                    break

        if verrors:
            raise verrors

        legacy_replication_tasks = await self._legacy_replication_tasks()
        if self._is_legacy(new, legacy_replication_tasks):
            verrors.add_child(f'periodic_snapshot_update', self._validate_legacy(new))
        else:
            if self._is_legacy(old, legacy_replication_tasks):
                verrors.add(
                    'periodic_snapshot_update.naming_schema',
                    ('This snapshot task is being used in legacy replication task. You must use naming schema '
                     f'{self._legacy_naming_schema(new)!r}. Please upgrade your replication tasks to edit this field.')
                )

        if verrors:
            raise verrors

        Cron.convert_schedule_to_db_format(new, begin_end=True)

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

    async def _validate(self, data):
        verrors = ValidationErrors()

        if data['dataset'] not in (await self.middleware.call('pool.filesystem_choices')):
            verrors.add(
                'dataset',
                'Invalid ZFS dataset'
            )

        if not data['recursive'] and data['exclude']:
            verrors.add(
                'exclude',
                'Excluding datasets has no sense for non-recursive periodic snapshot tasks'
            )

        for i, v in enumerate(data['exclude']):
            if not v.startswith(f'{data["dataset"]}/'):
                verrors.add(
                    f'exclude.{i}',
                    'Excluded dataset should be a child of selected dataset'
                )

        return verrors

    def _validate_legacy(self, data):
        verrors = ValidationErrors()

        if data['exclude']:
            verrors.add(
                'exclude',
                ('Excluding child datasets is not available because this snapshot task is being used in '
                 'legacy replication task. Please upgrade your replication tasks to edit this field.'),
            )

        return verrors

    def _is_legacy(self, data, legacy_replication_tasks):
        if data['naming_schema'] == self._legacy_naming_schema(data):
            for replication_task in legacy_replication_tasks:
                if (
                    data['dataset'] == replication_task['source_datasets'][0] or
                    (data['recursive'] and is_child(replication_task['source_datasets'][0], data['dataset'])) or
                    (replication_task['recursive'] and
                         is_child(data['dataset'], replication_task['source_datasets'][0]))
                ):
                    return True

        return False

    def _legacy_naming_schema(self, data):
        return f'auto-%Y%m%d.%H%M%S-{data["lifetime_value"]}{data["lifetime_unit"].lower()[0]}'

    async def _legacy_replication_tasks(self):
        return await self.middleware.call('replication.query', [['transport', '=', 'LEGACY']])
