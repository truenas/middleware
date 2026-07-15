from __future__ import annotations

from dataclasses import dataclass
import os
from typing import TYPE_CHECKING, Any

from middlewared.alert.base import (
    AlertCategory,
    AlertClassConfig,
    AlertLevel,
    OneShotAlertClass,
)
from middlewared.api.current import CloudSyncCreate, CloudSyncEntry, CloudSyncListDirectory, CloudSyncUpdate
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.service import ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.utils.path import FSLocation

from .directory import list_directory

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.main import Middleware


class CloudSyncModel(CloudTaskModelMixin, sa.Model):
    __tablename__ = "tasks_cloudsync"

    direction = sa.Column(sa.String(10))
    transfer_mode = sa.Column(sa.String(20))
    bwlimit = sa.Column(sa.JSON(list))
    transfers = sa.Column(sa.Integer(), nullable=True)

    encryption = sa.Column(sa.Boolean())
    filename_encryption = sa.Column(sa.Boolean())
    encryption_password = sa.Column(sa.EncryptedText())
    encryption_salt = sa.Column(sa.EncryptedText())

    create_empty_src_dirs = sa.Column(sa.Boolean())
    follow_symlinks = sa.Column(sa.Boolean())


@dataclass(kw_only=True)
class CloudSyncTaskFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.ERROR,
        title="Cloud Sync Task Failed",
        text='Cloud sync task "%(name)s" failed.',
    )

    id: int
    name: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["id"]

    @classmethod
    async def load(cls, middleware: Middleware, alerts: list[Any]) -> list[Any]:
        task_ids = {str(task.id) for task in await middleware.call2(middleware.services.cloudsync.query)}
        return [alert for alert in alerts if alert.key in task_ids]


class CloudProviderRemovedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.INFO,
        title="Cloud Provider Was Removed",
        text=(
            "%(provider)s is no longer a supported Cloud Credential. All previously configured Cloud Tasks have been "
            "deleted."
        ),
        deleted_automatically=False,
    )


class CloudSyncServicePart(CloudTaskServiceMixin[CloudSyncEntry, CloudSyncCreate, CloudSyncUpdate]):
    _datastore = "tasks.cloudsync"
    _entry = CloudSyncEntry
    schema_prefix = "cloud_sync"

    allow_zvol = False
    allowed_path_types = [FSLocation.LOCAL]
    path_field = "path"

    async def sharing_task_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> Any:
        return {
            "task_state": await self.call2(self.s.cloudsync.get_task_state_context),
        }

    async def sharing_task_extend(self, data: dict[str, Any], service_context: Any) -> dict[str, Any]:
        data["credentials"] = await self.call2(self.s.cloudsync.credentials.extend, data.pop("credential"))

        if job := await self.call2(self.s.cloudsync.get_task_state_job, service_context["task_state"], data["id"]):
            data["job"] = job

        convert_db_format_to_schedule(data)
        return data

    async def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data["credential"] = data.pop("credentials")
        convert_schedule_to_db_format(data)
        data.pop("job", None)
        data.pop(self.locked_field, None)
        return data

    async def _pre_delete(self, id_: int) -> None:
        await self.call2(self.s.cloudsync.abort, id_)
        await self.call2(self.s.alert.oneshot_delete, "CloudSyncTaskFailed", id_)

    def _basic_validate(self, verrors: ValidationErrors, name: str, entry: Any) -> None:
        # `entry` is polymorphic here (create/update/entry model *or* `CloudSyncListDirectory`), all of which
        # carry the encryption fields; typing it `Any` keeps the override compatible with the base signature.
        if entry.encryption:
            if not entry.encryption_password.get_secret_value():
                verrors.add(f"{name}.encryption_password", "This field is required when encryption is enabled")

        super()._basic_validate(verrors, name, entry)

    def _validate(
        self,
        app: App | None,
        verrors: ValidationErrors,
        name: str,
        entry: CloudSyncCreate | CloudSyncEntry,
    ) -> None:
        super()._validate(app, verrors, name, entry)

        for i, (limit1, limit2) in enumerate(zip(entry.bwlimit, entry.bwlimit[1:])):
            if limit1.time >= limit2.time:
                verrors.add(f"{name}.bwlimit.{i + 1}.time", f"Invalid time order: {limit1.time}, {limit2.time}")

        if entry.snapshot:
            if entry.direction != "PUSH":
                verrors.add(f"{name}.snapshot", "This option can only be enabled for PUSH tasks")
            if entry.transfer_mode == "MOVE":
                verrors.add(f"{name}.snapshot", "This option can not be used for MOVE transfer mode")

        # Listing the remote folder is a live provider call; only attempt it once everything cheap has passed.
        if not verrors:
            self._validate_folder(verrors, name, entry)

    def _validate_folder(
        self,
        verrors: ValidationErrors,
        name: str,
        entry: CloudSyncCreate | CloudSyncEntry,
    ) -> None:
        if entry.direction == "PULL":
            folder = entry.attributes.folder.rstrip("/")
            if folder:
                folder_parent = os.path.normpath(os.path.join(folder, ".."))
                if folder_parent == ".":
                    folder_parent = ""
                folder_basename = os.path.basename(folder)
                ls = list_directory(
                    self,
                    CloudSyncListDirectory(
                        credentials=self._credential_id(entry),
                        encryption=entry.encryption,
                        filename_encryption=entry.filename_encryption,
                        encryption_password=entry.encryption_password,
                        encryption_salt=entry.encryption_salt,
                        attributes=entry.attributes.model_copy(update={"folder": folder_parent}),
                        args=entry.args,
                    ),
                )
                for item in ls:
                    if item["Name"] == folder_basename:
                        if not item["IsDir"]:
                            verrors.add(f"{name}.attributes.folder", "This is not a directory")
                        break
                else:
                    verrors.add(f"{name}.attributes.folder", "Directory does not exist")

        if entry.direction == "PUSH":
            credentials = self._get_credentials(self._credential_id(entry))
            assert credentials is not None  # `_basic_validate` (via `_validate`) already rejected invalid credentials

            provider = REMOTES[credentials.provider.type]

            if provider.readonly:
                verrors.add(f"{name}.direction", "This remote is read-only")
