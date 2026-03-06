from __future__ import annotations

import contextlib
from typing import Any, TypeVar

import middlewared.sqlalchemy as sa
from middlewared.api.current import CronJobCreate, CronJobEntry, CronJobUpdate
from middlewared.service import CRUDServicePart, ValidationErrors
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format

CronJobCreateT = TypeVar('CronJobCreateT', bound=CronJobCreate)


class CronJobModel(sa.Model):
    __tablename__ = 'tasks_cronjob'

    id = sa.Column(sa.Integer(), primary_key=True)
    cron_minute = sa.Column(sa.String(100), default="00")
    cron_hour = sa.Column(sa.String(100), default="*")
    cron_daymonth = sa.Column(sa.String(100), default="*")
    cron_month = sa.Column(sa.String(100), default='*')
    cron_dayweek = sa.Column(sa.String(100), default="*")
    cron_user = sa.Column(sa.String(60))
    cron_command = sa.Column(sa.Text())
    cron_description = sa.Column(sa.String(200))
    cron_enabled = sa.Column(sa.Boolean(), default=True)
    cron_stdout = sa.Column(sa.Boolean(), default=True)
    cron_stderr = sa.Column(sa.Boolean(), default=False)


class CronJobServicePart(CRUDServicePart[CronJobEntry]):
    _datastore = 'tasks.cronjob'
    _datastore_prefix = 'cron_'
    _entry = CronJobEntry

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        convert_db_format_to_schedule(data)
        return data

    async def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        convert_schedule_to_db_format(data)
        return data

    async def do_create(self, data: CronJobCreate) -> CronJobEntry:
        data = await self.validate(data, 'cron_job_create')
        cronjob_entry = await self._create(data.model_dump())
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)
        return cronjob_entry

    async def do_update(self, id_: int, data: CronJobUpdate) -> CronJobEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)
        new = await self.validate(new, 'cron_job_update')
        cronjob_entry = await self._update(id_, new.model_dump())
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)
        return cronjob_entry

    async def do_delete(self, id_: int) -> None:
        await self.get_instance(id_)
        await self._delete(id_)
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

    async def validate(self, data: CronJobCreateT, schema: str) -> CronJobCreateT:
        verrors = ValidationErrors()

        # Windows users can have spaces in their usernames
        # http://www.freebsd.org/cgi/query-pr.cgi?pr=164808
        if ' ' in data.user:
            verrors.add(
                f'{schema}.user',
                'Usernames cannot have spaces'
            )
        else:
            user_data = None
            with contextlib.suppress(KeyError):
                user_data = await self.middleware.call('user.get_user_obj', {'username': data.user})

            if not user_data:
                verrors.add(
                    f'{schema}.user',
                    'Specified user does not exist'
                )
            elif user_data['pw_name'] != data.user:
                # Normalize to the canonical name from NSS to avoid
                # issues with backends that accept multiple name formats.
                data = data.model_copy(update={'user': user_data['pw_name']})

        if not data.command:
            verrors.add(
                f'{schema}.command',
                'Please specify a command for cronjob task.'
            )

        verrors.check()
        return data
