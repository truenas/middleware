from __future__ import annotations

from datetime import time
from typing import Any

import middlewared.sqlalchemy as sa
from middlewared.api.current import (
    PeriodicSnapshotTaskEntry, PoolSnapshotTaskCreate, PoolSnapshotTaskUpdate,
    PoolSnapshotTaskDeleteOptions, PoolSnapshotTaskUpdateWillChangeRetentionFor,
)
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.utils.lang import undefined
from middlewared.utils.path import is_child
from middlewared.utils.types import AuditCallback


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


class PeriodicSnapshotTaskServicePart(CRUDServicePart[PeriodicSnapshotTaskEntry]):
    _datastore = 'storage.task'
    _datastore_prefix = 'task_'
    _entry = PeriodicSnapshotTaskEntry

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return {
            'state': await self.middleware.call('zettarepl.get_state'),
            'vmware': await self.middleware.call('vmware.query'),
        }

    def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
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

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        convert_schedule_to_db_format(data, begin_end=True)
        for key in ('vmware_sync', 'state'):
            data.pop(key, None)
        return data

    async def do_create(self, data: PoolSnapshotTaskCreate) -> PeriodicSnapshotTaskEntry:
        verrors = ValidationErrors()
        verrors.add_child('periodic_snapshot_create', await self._validate(data))
        verrors.check()

        entry = await self._create(data.model_dump())
        await self.middleware.call('zettarepl.update_tasks')
        return entry

    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: PoolSnapshotTaskUpdate,
    ) -> PeriodicSnapshotTaskEntry:
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
        if data.fixate_removal_date != undefined:  # type: ignore[comparison-overlap]
            dump = data.model_dump()
            dump.pop('fixate_removal_date')
            will_change_retention_for = await self.call2(
                self.s.pool.snapshottask.update_will_change_retention_for, id_,
                PoolSnapshotTaskUpdateWillChangeRetentionFor(**dump),
            )

        entry = await self._update(id_, new.model_dump())

        if will_change_retention_for:
            await self.call2(self.s.pool.snapshottask.fixate_removal_date, will_change_retention_for, old)

        await self.middleware.call('zettarepl.update_tasks')
        return entry

    async def do_delete(
        self,
        audit_callback: AuditCallback,
        id_: int,
        options: PoolSnapshotTaskDeleteOptions,
    ) -> None:
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

        await self._delete(id_)
        await self.middleware.call('zettarepl.update_tasks')

    async def _validate(self, data: PeriodicSnapshotTaskEntry | PoolSnapshotTaskCreate) -> ValidationErrors:
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
