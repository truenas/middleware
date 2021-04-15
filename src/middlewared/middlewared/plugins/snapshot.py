from datetime import time
import os

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import accepts, Bool, Cron, Dataset, Dict, Int, List, Patch, Str
from middlewared.service import CallError, CRUDService, item_method, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.path import is_child
from middlewared.validators import ReplicationSnapshotNamingSchema


class PeriodicSnapshotTaskModel(sa.Model):
    __tablename__ = 'storage_task'

    id = sa.Column(sa.Integer(), primary_key=True)
    task_dataset = sa.Column(sa.String(150))
    task_recursive = sa.Column(sa.Boolean(), default=False)
    task_lifetime_value = sa.Column(sa.Integer(), default=2)
    task_lifetime_unit = sa.Column(sa.String(120), default='WEEK')
    task_begin = sa.Column(sa.Time(), default=time(hour=9))
    task_end = sa.Column(sa.Time(), default=time(hour=18))
    task_enabled = sa.Column(sa.Boolean(), default=True)
    task_exclude = sa.Column(sa.JSON(type=list))
    task_naming_schema = sa.Column(sa.String(150), default='auto-%Y-%m-%d_%H-%M')
    task_minute = sa.Column(sa.String(100), default="00")
    task_hour = sa.Column(sa.String(100), default="*")
    task_daymonth = sa.Column(sa.String(100), default="*")
    task_month = sa.Column(sa.String(100), default='*')
    task_dayweek = sa.Column(sa.String(100), default="*")
    task_allow_empty = sa.Column(sa.Boolean(), default=True)


class PeriodicSnapshotTaskService(CRUDService):

    class Config:
        datastore = 'storage.task'
        datastore_prefix = 'task_'
        datastore_extend = 'pool.snapshottask.extend'
        datastore_extend_context = 'pool.snapshottask.extend_context'
        namespace = 'pool.snapshottask'
        cli_namespace = 'task.snapshot'

    @private
    async def extend_context(self, rows, extra):
        return {
            'state': await self.middleware.call('zettarepl.get_state'),
            'vmware': await self.middleware.call('vmware.query'),
        }

    @private
    async def extend(self, data, context):
        Cron.convert_db_format_to_schedule(data, begin_end=True)

        data['vmware_sync'] = any(
            (
                vmware['filesystem'] == data['dataset'] or
                (data['recursive'] and is_child(vmware['filesystem'], data['dataset']))
            )
            for vmware in context['vmware']
        )

        if 'error' in context['state']:
            data['state'] = context['state']['error']
        else:
            data['state'] = context['state']['tasks'].get(f'periodic_snapshot_task_{data["id"]}', {
                'state': 'PENDING',
            })

        return data

    @accepts(
        Dict(
            'periodic_snapshot_create',
            Dataset('dataset', required=True),
            Bool('recursive', required=True),
            List('exclude', items=[Dataset('item')]),
            Int('lifetime_value', required=True),
            Str('lifetime_unit', enum=['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'], required=True),
            Str('naming_schema', required=True, validators=[ReplicationSnapshotNamingSchema()]),
            Cron(
                'schedule',
                defaults={
                    'minute': '00',
                    'begin': '00:00',
                    'end': '23:59',
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
        or zvols from the snapshot.
        Snapshots will be automatically destroyed after a certain amount of time, specified by
        `lifetime_value` and `lifetime_unit`.
        If multiple periodic tasks create snapshots at the same time (for example hourly and daily at 00:00) the snapshot
        will be kept until the last of these tasks reaches its expiry time.
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

        Cron.convert_schedule_to_db_format(data, begin_end=True)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('zettarepl.update_tasks')

        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch(
            'periodic_snapshot_create',
            'periodic_snapshot_update',
            ('add', {'name': 'fixate_removal_date', 'type': 'bool'}),
            ('attr', {'update': True})
        ),
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

        fixate_removal_date = data.pop('fixate_removal_date', False)

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

        Cron.convert_schedule_to_db_format(new, begin_end=True)

        for key in ('vmware_sync', 'state'):
            new.pop(key, None)

        will_change_retention_for = None
        if fixate_removal_date:
            will_change_retention_for = await self.middleware.call(
                'pool.snapshottask.update_will_change_retention_for', id, data,
            )

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if will_change_retention_for:
            await self.middleware.call('pool.snapshottask.fixate_removal_date', will_change_retention_for, old)

        await self.middleware.call('zettarepl.update_tasks')

        return await self._get_instance(id)

    @accepts(
        Int('id'),
        Dict(
            'options',
             Bool('fixate_removal_date', default=False),
        ),
    )
    async def do_delete(self, id, options):
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

        for replication_task in await self.middleware.call('replication.query', [
            ['direction', '=', 'PUSH'],
            ['also_include_naming_schema', '=', []],
            ['enabled', '=', True],
        ]):
            if len(replication_task['periodic_snapshot_tasks']) == 1:
                if replication_task['periodic_snapshot_tasks'][0]['id'] == id:
                    raise CallError(
                        f'You are deleting the last periodic snapshot task bound to enabled replication task '
                        f'{replication_task["name"]!r} which will break it. Please, disable that replication task '
                        f'first.',
                    )

        if options['fixate_removal_date']:
            will_change_retention_for = await self.middleware.call(
                'pool.snapshottask.delete_will_change_retention_for', id
            )

            if will_change_retention_for:
                task = await self.get_instance(id)
                await self.middleware.call('pool.snapshottask.fixate_removal_date', will_change_retention_for, task)

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

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
                'ZFS dataset or zvol not found'
            )

        if not data['recursive'] and data['exclude']:
            verrors.add(
                'exclude',
                'Excluding datasets or zvols is not necessary for non-recursive periodic snapshot tasks'
            )

        for i, v in enumerate(data['exclude']):
            if not v.startswith(f'{data["dataset"]}/'):
                verrors.add(
                    f'exclude.{i}',
                    'Excluded dataset or zvol should be a child or other descendant of selected dataset'
                )

        return verrors


class PeriodicSnapshotTaskFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'snapshottask'
    title = 'Snapshot Task'
    resource_name = 'dataset'

    async def query(self, path, enabled, options=None):
        results = []
        for task in await self.middleware.call('pool.snapshottask.query', [['enabled', '=', enabled]]):
            if is_child(os.path.join('/mnt', task['dataset']), path):
                results.append(task)

        return results

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', 'storage.task', attachment['id'])

        await self.middleware.call('zettarepl.update_tasks')

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            await self.middleware.call('datastore.update', 'storage.task', attachment['id'], {'task_enabled': enabled})

        await self.middleware.call('zettarepl.update_tasks')


async def on_zettarepl_state_changed(middleware, id, fields):
    if id.startswith('periodic_snapshot_task_'):
        task_id = int(id.split('_')[-1])
        middleware.send_event('pool.snapshottask.query', 'CHANGED', id=task_id, fields={'state': fields})


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate',
                          PeriodicSnapshotTaskFSAttachmentDelegate(middleware))

    middleware.register_hook('zettarepl.state_change', on_zettarepl_state_changed)
