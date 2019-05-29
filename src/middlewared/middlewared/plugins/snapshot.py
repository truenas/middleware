from middlewared.schema import accepts, Bool, Cron, Dict, Int, List, Patch, Path, Str
from middlewared.service import CallError, CRUDService, item_method, private, ValidationErrors
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
            'state': await self.middleware.call('zettarepl.get_state'),
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

        data['state'] = context['state'].get(f'periodic_snapshot_task_{data["id"]}', {
            'state': 'PENDING',
        })

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
            Cron(
                'schedule',
                defaults={
                    'minute': '00',
                    'begin': '09:00',
                    'end': '18:00'
                },
                required=True,
                begin_end=True
            ),
            Bool('allow_empty', default=True),
            Bool('enabled', default=True),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a Periodic Snapshot Task

        Create a Periodic Snapshot Task that will take snapshots of specified `dataset` at specified `schedule`.
        Recursive snapshots can be created if `recursive` flag is enabled. You can `exclude` specific child datasets
        from snapshot.
        Snapshots will be automatically destroyed after a certain amount of time, specified by
        `lifetime_value` and `lifetime_unit`.
        Snapshots will be named according to `naming_schema` which is a `strftime`-like template for snapshot name
        and must contain `%Y`, `%m`, `%d`, `%H` and `%M`.

        .. examples(websocket)::

          Create a recursive Periodic Snapshot Task for dataset `data/work` excluding `data/work/temp`. Snapshots
          will be created on weekdays every hour from 09:00 to 18:00 and will be stored for two weeks.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.snapshottask.create",
                "params": [{
                    "dataset": "data/work",
                    "recursive": true,
                    "exclude": ["data/work/temp"],
                    "lifetime_value": 2,
                    "lifetime_unit": "WEEK",
                    "naming_schema": "auto_%Y-%m-%d_%H-%M",
                    "schedule": {
                        "minute": "0",
                        "hour": "*",
                        "dom": "*",
                        "month": "*",
                        "dow": "1,2,3,4,5",
                        "begin": "09:00",
                        "end": "18:00"
                    }
                }]
            }
        """

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
        await self.middleware.call('zettarepl.update_tasks')

        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch('periodic_snapshot_create', 'periodic_snapshot_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        """
        Update a Periodic Snapshot Task with specific `id`

        See the documentation for `create` method for information on payload contents

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.snapshottask.update",
                "params": [
                    1,
                    {
                        "dataset": "data/work",
                        "recursive": true,
                        "exclude": ["data/work/temp"],
                        "lifetime_value": 2,
                        "lifetime_unit": "WEEK",
                        "naming_schema": "auto_%Y-%m-%d_%H-%M",
                        "schedule": {
                            "minute": "0",
                            "hour": "*",
                            "dom": "*",
                            "month": "*",
                            "dow": "1,2,3,4,5",
                            "begin": "09:00",
                            "end": "18:00"
                        }
                    }
                ]
            }
        """

        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        verrors.add_child('periodic_snapshot_update', await self._validate(new))

        if not new['enabled']:
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

        for key in ('legacy', 'vmware_sync', 'state'):
            new.pop(key, None)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.restart', 'cron')
        await self.middleware.call('zettarepl.update_tasks')

        return await self._get_instance(id)

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):
        """
        Delete a Periodic Snapshot Task with specific `id`

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.snapshottask.delete",
                "params": [
                    1
                ]
            }
        """

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call('service.restart', 'cron')
        await self.middleware.call('zettarepl.update_tasks')

        return response

    @item_method
    @accepts(Int("id"))
    async def run(self, id):
        """
        Execute a Periodic Snapshot Task of `id`.
        """
        task = await self._get_instance(id)

        if not task["enabled"]:
            raise CallError("Task is not enabled")

        await self.middleware.call("zettarepl.run_periodic_snapshot_task", task["id"])

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

        if not data['allow_empty']:
            verrors.add(
                'allow_empty',
                ('Disallowing empty snapshots is not available because this snapshot task is being used in '
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
