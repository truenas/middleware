from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass
from middlewared.api.current import CloudBackupCreate, CloudBackupEntry, CloudBackupUpdate
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.service import CallError, SharingTaskServicePart, ValidationErrors
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


class CloudBackupServicePart(SharingTaskServicePart[CloudBackupEntry], CloudTaskServiceMixin):
    _datastore = "tasks.cloud_backup"
    _entry = CloudBackupEntry

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

    async def do_create(self, app: App | None, data: CloudBackupCreate) -> CloudBackupEntry:
        cloud_backup = await self.to_thread(self._run_validation, app, "cloud_backup_create", data)
        entry = await self._create(cloud_backup)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_update(self, app: App | None, id_: int, data: CloudBackupUpdate) -> CloudBackupEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)
        cloud_backup = await self.to_thread(self._run_validation, app, "cloud_backup_update", new)
        entry = await self._update(id_, cloud_backup)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_delete(self, id_: int) -> None:
        await self.call2(self.s.cloud_backup.abort, id_)
        await self.call2(self.s.alert.oneshot_delete, "CloudBackupTaskFailed", id_)
        await self._delete(id_)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)

    async def get_path_field(self, data: Any) -> Any:
        if isinstance(data, dict):
            return data[self.path_field]
        return getattr(data, self.path_field)

    def validate_zvol(self, path: str) -> None:
        dataset = zvol_path_to_name(path)
        if not (
            self.call_sync2(self.s.vm.query_snapshot_begin, dataset, False) or
            self.middleware.call_sync("vmware.dataset_has_vms", dataset, False)
        ):
            raise CallError("Backed up zvol must be used by a local or VMware VM")

    def _run_validation(self, app: App | None, schema: str, entry: CloudBackupEntry) -> dict[str, Any]:
        # FIXME: Drop this model->dict marshalling and validate the entry directly once CloudTaskServiceMixin
        # is converted; it is shared with the unconverted cloud_sync and only operates on dicts for now.
        data = entry.model_dump(expose_secrets=True)
        data.pop(self.locked_field, None)
        data.pop("job", None)
        # credentials is a foreign key; collapse the extended entry back to its id for the
        # datastore and the shared validation mixin (a changed credential is already an int).
        if isinstance(data["credentials"], dict):
            data["credentials"] = data["credentials"]["id"]

        verrors = ValidationErrors()
        self._validate(app, verrors, schema, data)
        if not verrors:
            credentials = resolve_credentials(self, entry.credentials)
            try:
                # Route through the registry method so the suite can mock cloud_backup.ensure_initialized.
                self.call_sync2(self.s.cloud_backup.ensure_initialized, entry, credentials)
            except IncorrectPassword as e:
                verrors.add(f"{schema}.password", e.errmsg)
        verrors.check()
        return data

    def _validate(self, app: App | None, verrors: ValidationErrors, name: str, data: dict[str, Any]) -> None:
        # CloudTaskServiceMixin is shared with the unconverted cloud_sync and operates on the dict
        # (it normalizes data["attributes"] in place, which must reach the datastore).
        super()._validate(app, verrors, name, data)  # type: ignore[no-untyped-call]

        if data["snapshot"] and data["absolute_paths"]:
            verrors.add(f"{name}.snapshot", "This option can't be used when absolute paths are enabled")

        if data["cache_path"]:
            self.middleware.run_coroutine(
                check_path_resides_within_volume(
                    verrors, self.middleware, f"{name}.cache_path", data["cache_path"], True,
                )
            )
            if not verrors:
                statfs = self.middleware.call_sync("filesystem.statfs", data["cache_path"])
                if "RO" in statfs.flags:
                    verrors.add(f"{name}.cache_path", "The cache directory must be writeable")
