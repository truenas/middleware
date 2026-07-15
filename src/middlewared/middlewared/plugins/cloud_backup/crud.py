from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass
from middlewared.api.current import CloudBackupCreate, CloudBackupEntry, CloudBackupUpdate
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.service import CallError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.utils.path import FSLocation

from .init import IncorrectPassword
from .utils import resolve_credentials

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App


class CloudBackupModel(CloudTaskModelMixin, sa.Model):
    __tablename__ = "tasks_cloud_backup"

    password = sa.Column(sa.EncryptedText())
    keep_last = sa.Column(sa.Integer())
    transfer_setting = sa.Column(sa.String(16))
    absolute_paths = sa.Column(sa.Boolean())
    cache_path = sa.Column(sa.Text(), nullable=True)
    rate_limit = sa.Column(sa.Integer(), nullable=True)


@dataclass(kw_only=True)
class CloudBackupTaskFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.ERROR,
        title="Cloud Backup Task Failed",
        text="Cloud backup task \"%(name)s\" failed.",
    )

    id: int
    name: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["id"]


class CloudBackupServicePart(CloudTaskServiceMixin[CloudBackupEntry, CloudBackupCreate, CloudBackupUpdate]):
    _datastore = "tasks.cloud_backup"
    _entry = CloudBackupEntry
    schema_prefix = "cloud_backup"

    allow_zvol = True
    allowed_path_types = [FSLocation.LOCAL]
    path_field = "path"

    async def sharing_task_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> Any:
        return {
            "task_state": await self.call2(self.s.cloud_backup.get_task_state_context),
        }

    async def sharing_task_extend(self, data: dict[str, Any], service_context: Any) -> dict[str, Any]:
        data["credentials"] = await self.call2(self.s.cloudsync.credentials.extend, data.pop("credential"))

        if job := await self.call2(self.s.cloud_backup.get_task_state_job, service_context["task_state"], data["id"]):
            data["job"] = job

        convert_db_format_to_schedule(data)
        return data

    async def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data["credential"] = data.pop("credentials")
        convert_schedule_to_db_format(data)
        # tasks_cloud_backup.job is NOT NULL; the runtime job state lives in task_state, so persist null here.
        data["job"] = None
        data.pop(self.locked_field, None)
        return data

    async def _pre_delete(self, id_: int) -> None:
        await self.call2(self.s.cloud_backup.abort, id_)
        await self.call2(self.s.alert.oneshot_delete, "CloudBackupTaskFailed", id_)

    def validate_zvol(self, path: str) -> None:
        dataset = zvol_path_to_name(path)
        if not (
            self.call_sync2(self.s.vm.query_snapshot_begin, dataset, False) or
            self.middleware.call_sync("vmware.dataset_has_vms", dataset, False)
        ):
            raise CallError("Backed up zvol must be used by a local or VMware VM")

    def _validate(
        self, app: App | None, verrors: ValidationErrors, name: str, entry: CloudBackupCreate | CloudBackupEntry,
    ) -> None:
        super()._validate(app, verrors, name, entry)

        if entry.snapshot and entry.absolute_paths:
            verrors.add(f"{name}.snapshot", "This option can't be used when absolute paths are enabled")

        if entry.cache_path:
            self.middleware.run_coroutine(
                check_path_resides_within_volume(
                    verrors, self.middleware, f"{name}.cache_path", entry.cache_path, True,
                )
            )
            if not verrors:
                statfs = self.middleware.call_sync("filesystem.statfs", entry.cache_path)
                if "RO" in statfs.flags:
                    verrors.add(f"{name}.cache_path", "The cache directory must be writeable")

        if not verrors:
            credentials = resolve_credentials(self, entry.credentials)
            try:
                self.call_sync2(self.s.cloud_backup.ensure_initialized, entry, credentials)
            except IncorrectPassword as e:
                verrors.add(f"{name}.password", e.errmsg)
