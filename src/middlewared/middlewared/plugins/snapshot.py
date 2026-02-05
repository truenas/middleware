from datetime import time
import os
import typing

from middlewared.api import api_method
from middlewared.api.current import (
    PeriodicSnapshotTaskEntry, PeriodicSnapshotTaskCreateArgs, PeriodicSnapshotTaskCreateResult,
    PeriodicSnapshotTaskUpdateArgs, PeriodicSnapshotTaskUpdateResult,
    PeriodicSnapshotTaskDeleteArgs, PeriodicSnapshotTaskDeleteResult,
    PeriodicSnapshotTaskMaxCountArgs, PeriodicSnapshotTaskMaxCountResult, PeriodicSnapshotTaskMaxTotalCountArgs,
    PeriodicSnapshotTaskMaxTotalCountResult, PeriodicSnapshotTaskRunArgs, PeriodicSnapshotTaskRunResult,
    PoolSnapshotTaskCreate, PoolSnapshotTaskUpdate, PoolSnapshotTaskDeleteOptions,
    PoolSnapshotTaskUpdateWillChangeRetentionFor,
)
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.service import CallError, CRUDService, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.utils.lang import undefined
from middlewared.utils.path import is_child
from middlewared.utils.types import AuditCallback

from .snapshot_.removal_date import PeriodicSnapshotTaskService as RemovalDateService
from .snapshot_.task_retention import PeriodicSnapshotTaskService as TaskRetentionService


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
    task_exclude = sa.Column(sa.JSON(list))
    task_naming_schema = sa.Column(sa.String(150), default='auto-%Y-%m-%d_%H-%M')
    task_minute = sa.Column(sa.String(100), default="00")
    task_hour = sa.Column(sa.String(100), default="*")
    task_daymonth = sa.Column(sa.String(100), default="*")
    task_month = sa.Column(sa.String(100), default='*')
    task_dayweek = sa.Column(sa.String(100), default="*")
    task_allow_empty = sa.Column(sa.Boolean(), default=True)
    task_state = sa.Column(sa.Text(), default='{}')


class PeriodicSnapshotTaskService(RemovalDateService, TaskRetentionService, CRUDService[PeriodicSnapshotTaskEntry]):

    class Config:
        datastore = 'storage.task'
        datastore_prefix = 'task_'
        datastore_extend = 'pool.snapshottask.extend'
        datastore_extend_context = 'pool.snapshottask.extend_context'
        namespace = 'pool.snapshottask'
        cli_namespace = 'task.snapshot'
        entry = PeriodicSnapshotTaskEntry
        role_prefix = 'SNAPSHOT_TASK'
        generic = True

    @private
    async def extend_context(self, rows, extra):
        return {
            'state': await self.middleware.call('zettarepl.get_state'),
            'vmware': await self.middleware.call('vmware.query'),
        }

    @private
    async def extend(self, data, context):
        convert_db_format_to_schedule(data, begin_end=True)

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

    @api_method(
        PeriodicSnapshotTaskCreateArgs,
        PeriodicSnapshotTaskCreateResult,
        audit='Snapshot task create:',
        audit_extended=lambda data: data['dataset'],
        check_annotations=True,
    )
    async def do_create(self, data: PoolSnapshotTaskCreate) -> PeriodicSnapshotTaskEntry:
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
        """

        verrors = ValidationErrors()

        verrors.add_child('periodic_snapshot_create', await self._validate(data))

        verrors.check()

        new = data.model_dump()
        convert_schedule_to_db_format(new, begin_end=True)

        id_ = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('zettarepl.update_tasks')

        return await self.get_instance(id_)

    @api_method(
        PeriodicSnapshotTaskUpdateArgs,
        PeriodicSnapshotTaskUpdateResult,
        audit='Snapshot task update:',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: PoolSnapshotTaskUpdate,
    ) -> PeriodicSnapshotTaskEntry:
        """
        Update a Periodic Snapshot Task with specific `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(old.dataset)
        new = old.updated(data)

        verrors = ValidationErrors()

        verrors.add_child('periodic_snapshot_update', await self._validate(new))

        if not new.enabled:
            for replication_task in await self.middleware.call('replication.query', [['enabled', '=', True]]):
                if any(periodic_snapshot_task['id'] == id_
                       for periodic_snapshot_task in replication_task['periodic_snapshot_tasks']):
                    verrors.add(
                        'periodic_snapshot_update.enabled',
                        (f'You can\'t disable this periodic snapshot task because it is bound to enabled replication '
                         f'task {replication_task["id"]!r}')
                    )
                    break

        verrors.check()

        will_change_retention_for = None
        if data.fixate_removal_date != undefined:
            dump = data.model_dump()
            dump.pop('fixate_removal_date')
            will_change_retention_for = await self.call2(
                self.s.pool.snapshottask.update_will_change_retention_for, id_,
                PoolSnapshotTaskUpdateWillChangeRetentionFor(**dump),
            )

        update = new.model_dump()
        convert_schedule_to_db_format(update, begin_end=True)
        for key in ('vmware_sync', 'state'):
            update.pop(key, None)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            update,
            {'prefix': self._config.datastore_prefix}
        )

        if will_change_retention_for:
            await self.call2(self.s.pool.snapshottask.fixate_removal_date, will_change_retention_for, old)

        await self.middleware.call('zettarepl.update_tasks')

        return await self.get_instance(id_)

    @api_method(
        PeriodicSnapshotTaskDeleteArgs,
        PeriodicSnapshotTaskDeleteResult,
        audit='Snapshot task delete:',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(
        self,
        audit_callback: AuditCallback,
        id_: int,
        options: PoolSnapshotTaskDeleteOptions,
    ) -> typing.Literal[True]:
        """
        Delete a Periodic Snapshot Task with specific `id`.
        """
        task = await self.get_instance(id_)
        audit_callback(task.dataset)

        for replication_task in await self.middleware.call('replication.query', [
            ['direction', '=', 'PUSH'],
            ['also_include_naming_schema', '=', []],
            ['enabled', '=', True],
        ]):
            if len(replication_task['periodic_snapshot_tasks']) == 1:
                if replication_task['periodic_snapshot_tasks'][0]['id'] == id_:
                    raise CallError(
                        f'You are deleting the last periodic snapshot task bound to enabled replication task '
                        f'{replication_task["name"]!r} which will break it. Please, disable that replication task '
                        f'first.',
                    )

        if options.fixate_removal_date:
            will_change_retention_for = await self.call2(self.s.pool.snapshottask.delete_will_change_retention_for, id_)

            if will_change_retention_for:
                await self.call2(self.s.pool.snapshottask.fixate_removal_date, will_change_retention_for, task)

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id_
        )

        await self.middleware.call('zettarepl.update_tasks')

        return response

    @api_method(
        PeriodicSnapshotTaskMaxCountArgs,
        PeriodicSnapshotTaskMaxCountResult,
        roles=['SNAPSHOT_TASK_READ'],
        check_annotations=True,
    )
    def max_count(self) -> int:
        """
        Returns a maximum amount of snapshots (per-dataset) the system can sustain.
        """

        # There is a limit to how many snapshots Windows will present to users through File Explorer. If we respond
        # with too many, then File Explorer will show no snapshots available.
        return 512

    @api_method(
        PeriodicSnapshotTaskMaxTotalCountArgs,
        PeriodicSnapshotTaskMaxTotalCountResult,
        roles=['SNAPSHOT_TASK_READ'],
        check_annotations=True,
    )
    def max_total_count(self) -> int:
        """
        Returns a maximum amount of snapshots (total) the system can sustain.
        """

        # Having too many snapshots results in various performance complications (mainly, when listing them).
        # This is a random round number that is large enough and does not cause issues in most use cases.
        return 10000

    @api_method(
        PeriodicSnapshotTaskRunArgs,
        PeriodicSnapshotTaskRunResult,
        roles=['SNAPSHOT_TASK_WRITE'],
        check_annotations=True,
    )
    async def run(self, id_: int) -> None:
        """
        Execute a Periodic Snapshot Task of `id`.
        """
        task = await self.get_instance(id_)

        if not task["enabled"]:
            raise CallError("Task is not enabled")

        await self.middleware.call("zettarepl.run_periodic_snapshot_task", task["id"])

    async def _validate(self, data: PeriodicSnapshotTaskEntry):
        verrors = ValidationErrors()

        if data.dataset not in (await self.middleware.call('pool.filesystem_choices')):
            verrors.add(
                'dataset',
                'Dataset not found'
            )

        if not data.recursive and data.exclude:
            verrors.add(
                'exclude',
                'Excluding datasets is not necessary for non-recursive periodic snapshot tasks'
            )

        for i, v in enumerate(data.exclude):
            if not v.startswith(f'{data.dataset}/'):
                verrors.add(
                    f'exclude.{i}',
                    'Excluded dataset should be a child or other descendant of the selected dataset'
                )

        return verrors


class PeriodicSnapshotTaskFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'snapshottask'
    title = 'Snapshot Task'
    resource_name = 'dataset'

    async def query(self, path: str, enabled: bool, options=None):
        results = []
        for task in await self.middleware.call2(
            self.middleware.services.pool.snapshottask.query,
            [['enabled', '=', enabled]],
        ):
            if await self.middleware.call('filesystem.is_child', os.path.join('/mnt', task.dataset), path):
                results.append(task)

        return results

    async def delete(self, attachments: list[PeriodicSnapshotTaskEntry]):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', 'storage.task', attachment.id)

        await self.middleware.call('zettarepl.update_tasks')

    async def toggle(self, attachments: list[PeriodicSnapshotTaskEntry], enabled: bool):
        for attachment in attachments:
            await self.middleware.call('datastore.update', 'storage.task', attachment.id, {'task_enabled': enabled})

        await self.middleware.call('zettarepl.update_tasks')


async def on_zettarepl_state_changed(middleware, id_, fields):
    if id_.startswith('periodic_snapshot_task_'):
        task_id = int(id_.split('_')[-1])
        middleware.send_event('pool.snapshottask.query', 'CHANGED', id=task_id, fields={'state': fields})


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate',
                          PeriodicSnapshotTaskFSAttachmentDelegate(middleware))

    middleware.register_hook('zettarepl.state_change', on_zettarepl_state_changed)
