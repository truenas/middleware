from __future__ import annotations

import shlex
from typing import Any

from middlewared.api.current import RsyncTaskCreate, RsyncTaskEntry, RsyncTaskUpdate
from middlewared.service import SharingTaskServicePart
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format

from .validate import validate_rsync_task


class RsyncTaskModel(sa.Model):
    __tablename__ = "tasks_rsync"

    id = sa.Column(sa.Integer(), primary_key=True)
    rsync_path = sa.Column(sa.String(255))
    rsync_dataset = sa.Column(sa.String(255), nullable=True)
    rsync_relative_path = sa.Column(sa.String(255), nullable=True)
    rsync_remotehost = sa.Column(sa.String(120), nullable=True)
    rsync_remoteport = sa.Column(sa.SmallInteger(), nullable=True)
    rsync_remotemodule = sa.Column(sa.String(120), nullable=True)
    rsync_ssh_credentials_id = sa.Column(sa.ForeignKey("system_keychaincredential.id"), index=True, nullable=True)
    rsync_desc = sa.Column(sa.String(120))
    rsync_minute = sa.Column(sa.String(100))
    rsync_hour = sa.Column(sa.String(100))
    rsync_daymonth = sa.Column(sa.String(100))
    rsync_month = sa.Column(sa.String(100))
    rsync_dayweek = sa.Column(sa.String(100))
    rsync_user = sa.Column(sa.String(60))
    rsync_recursive = sa.Column(sa.Boolean())
    rsync_times = sa.Column(sa.Boolean())
    rsync_compress = sa.Column(sa.Boolean())
    rsync_archive = sa.Column(sa.Boolean())
    rsync_delete = sa.Column(sa.Boolean())
    rsync_quiet = sa.Column(sa.Boolean())
    rsync_preserveperm = sa.Column(sa.Boolean())
    rsync_preserveattr = sa.Column(sa.Boolean())
    rsync_extra = sa.Column(sa.Text())
    rsync_enabled = sa.Column(sa.Boolean())
    rsync_mode = sa.Column(sa.String(20))
    rsync_remotepath = sa.Column(sa.String(255))
    rsync_direction = sa.Column(sa.String(10))
    rsync_delayupdates = sa.Column(sa.Boolean())
    rsync_job = sa.Column(sa.JSON(None))


class RsyncTaskServicePart(SharingTaskServicePart[RsyncTaskEntry]):
    _datastore = "tasks.rsync"
    _datastore_prefix = "rsync_"
    _entry = RsyncTaskEntry

    async def sharing_task_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> Any:
        return {
            "task_state": await self.call2(self.s.rsynctask.get_task_state_context),
        }

    async def sharing_task_extend(self, data: dict[str, Any], service_context: Any) -> dict[str, Any]:
        try:
            data["extra"] = shlex.split(data["extra"].replace('"', r'"\"').replace("'", r'"\"'))
        except ValueError:
            # This is to handle the case where the extra value is misconfigured for old cases
            # Moving on, we are going to verify that it can be split successfully using shlex
            data["extra"] = data["extra"].split()

        convert_db_format_to_schedule(data)
        if job := await self.call2(self.s.rsynctask.get_task_state_job, service_context["task_state"], data["id"]):
            data["job"] = job
        return data

    async def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data["extra"] = " ".join(data["extra"])
        convert_schedule_to_db_format(data)
        return data

    async def do_create(self, data: RsyncTaskCreate) -> RsyncTaskEntry:
        verrors, d = await validate_rsync_task(self, data.model_dump(), "rsync_task_create")
        verrors.check()

        entry = await self._create(d)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_update(self, id_: int, data: RsyncTaskUpdate) -> RsyncTaskEntry:
        old = (await self.get_instance(id_)).model_dump()
        old.pop(self.locked_field)
        old.pop("job")
        if old["ssh_credentials"]:
            old["ssh_credentials"] = old["ssh_credentials"]["id"]

        new = {**old, **data.model_dump()}
        new.setdefault("validate_rpath", True)
        new.setdefault("ssh_keyscan", False)

        verrors, new = await validate_rsync_task(self, new, "rsync_task_update")
        verrors.check()

        entry = await self._update(id_, new)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_delete(self, id_: int) -> None:
        await self._delete(id_)
        for klass in ("RsyncSuccess", "RsyncFailed"):
            await self.call2(self.s.alert.oneshot_delete, klass, id_)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
