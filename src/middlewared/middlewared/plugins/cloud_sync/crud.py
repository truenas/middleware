from __future__ import annotations

from dataclasses import dataclass
import itertools
import json
import os
import subprocess
from typing import TYPE_CHECKING, Any

from middlewared.alert.base import (
    AlertCategory,
    AlertClassConfig,
    AlertLevel,
    OneShotAlertClass,
)
from middlewared.api.current import (
    CloudSyncCreate,
    CloudSyncEntry,
    CloudSyncListDirectory,
    CloudSyncProvider,
    CloudSyncProviderTaskSchemaItem,
    CloudSyncSyncOptions,
    CloudSyncUpdate,
    CloudTaskAttributes,
    RestoreOpts,
)
from middlewared.plugins.cloud.crud import CloudTaskServiceMixin
from middlewared.plugins.cloud.model import CloudTaskModelMixin
from middlewared.plugins.cloud.path import get_remote_path
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.rclone.remote.storjix import StorjIxError
from middlewared.service import CallError, SharingTaskServicePart, ValidationError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format

from .credentials import extend_credential
from .rclone import (
    CloudSyncTask,
    FsLockDirection,
    FsLockManager,
    RcloneConfig,
    RcloneConfigParams,
    lsjson_error_excerpt,
    rclone,
)

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware

OAUTH_URL = "https://www.truenas.com/oauth"


@dataclass(kw_only=True)
class CloudSyncTaskFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.ERROR,
        title="Cloud Sync Task Failed",
        text="Cloud sync task \"%(name)s\" failed.",
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


class CloudSyncModel(CloudTaskModelMixin, sa.Model):
    __tablename__ = 'tasks_cloudsync'

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


class CloudSyncServicePart(SharingTaskServicePart[CloudSyncEntry], CloudTaskServiceMixin):
    _datastore = "tasks.cloudsync"
    _entry = CloudSyncEntry

    local_fs_lock_manager = FsLockManager()
    remote_fs_lock_manager = FsLockManager()

    async def sharing_task_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> Any:
        return {
            "task_state": await self.call2(self.s.cloudsync.get_task_state_context),
        }

    async def sharing_task_extend(self, data: dict[str, Any], service_context: Any) -> dict[str, Any]:
        data["credentials"] = extend_credential(data.pop("credential"))

        if job := await self.call2(self.s.cloudsync.get_task_state_job, service_context["task_state"], data["id"]):
            data["job"] = job

        convert_db_format_to_schedule(data)
        return data

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data["credential"] = data.pop("credentials")
        convert_schedule_to_db_format(data)
        data.pop("job", None)
        data.pop(self.locked_field, None)
        return data

    async def get_path_field(self, data: Any) -> Any:
        if isinstance(data, dict):
            return data[self.path_field]
        return getattr(data, self.path_field)

    def _basic_validate(self, verrors: ValidationErrors, name: str, data: dict[str, Any]) -> None:
        if data["encryption"]:
            if not data["encryption_password"]:
                verrors.add(f"{name}.encryption_password", "This field is required when encryption is enabled")

        super()._basic_validate(verrors, name, data)

    def _validate(self, app: App | None, verrors: ValidationErrors, name: str, data: dict[str, Any]) -> None:
        super()._validate(app, verrors, name, data)

        for i, (limit1, limit2) in enumerate(zip(data["bwlimit"], data["bwlimit"][1:])):
            if limit1["time"] >= limit2["time"]:
                verrors.add(f"{name}.bwlimit.{i + 1}.time", f"Invalid time order: {limit1['time']}, {limit2['time']}")

        if data["snapshot"]:
            if data["direction"] != "PUSH":
                verrors.add(f"{name}.snapshot", "This option can only be enabled for PUSH tasks")
            if data["transfer_mode"] == "MOVE":
                verrors.add(f"{name}.snapshot", "This option can not be used for MOVE transfer mode")

    def _validate_folder(self, verrors: ValidationErrors, name: str, data: dict[str, Any]) -> None:
        if data["direction"] == "PULL":
            folder = data["attributes"]["folder"].rstrip("/")
            if folder:
                folder_parent = os.path.normpath(os.path.join(folder, ".."))
                if folder_parent == ".":
                    folder_parent = ""
                folder_basename = os.path.basename(folder)
                ls = self.list_directory(CloudSyncListDirectory(
                    credentials=data["credentials"],
                    encryption=data["encryption"],
                    filename_encryption=data["filename_encryption"],
                    encryption_password=data["encryption_password"],
                    encryption_salt=data["encryption_salt"],
                    attributes=CloudTaskAttributes(**{**data["attributes"], "folder": folder_parent}),
                    args=data["args"],
                ))
                for item in ls:
                    if item["Name"] == folder_basename:
                        if not item["IsDir"]:
                            verrors.add(f"{name}.attributes.folder", "This is not a directory")
                        break
                else:
                    verrors.add(f"{name}.attributes.folder", "Directory does not exist")

        if data["direction"] == "PUSH":
            credentials = self._get_credentials(data["credentials"])
            assert credentials is not None

            provider = REMOTES[credentials.provider.type]

            if provider.readonly:
                verrors.add(f"{name}.direction", "This remote is read-only")

    def _run_validation(self, app: App | None, schema: str, entry: CloudSyncEntry) -> dict[str, Any]:
        data = entry.model_dump(by_alias=True, context={"expose_secrets": True})
        data.pop(self.locked_field, None)
        data.pop("job", None)
        # credentials is a foreign key; the shared validator works with the id.
        if isinstance(data["credentials"], dict):
            data["credentials"] = data["credentials"]["id"]

        verrors = ValidationErrors()
        self._validate(app, verrors, schema, data)
        verrors.check()
        self._validate_folder(verrors, schema, data)
        verrors.check()
        return data

    async def do_create(self, app: App | None, data: CloudSyncCreate) -> CloudSyncEntry:
        cloud_sync = await self.to_thread(self._run_validation, app, "cloud_sync_create", data)
        entry = await self._create(cloud_sync)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_update(self, app: App | None, id_: int, data: CloudSyncUpdate) -> CloudSyncEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)
        cloud_sync = await self.to_thread(self._run_validation, app, "cloud_sync_update", new)
        entry = await self._update(id_, cloud_sync)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_delete(self, id_: int) -> None:
        await self.call2(self.s.cloudsync.abort, id_)
        await self.call2(self.s.alert.oneshot_delete, "CloudSyncTaskFailed", id_)
        await self._delete(id_)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)

    def create_bucket(self, credentials_id: int, name: str) -> None:
        credentials = self._get_credentials(credentials_id)
        if not credentials:
            raise CallError("Invalid credentials")

        provider = REMOTES[credentials.provider.type]

        if not provider.can_create_bucket:
            raise CallError("This provider can't create buckets")

        try:
            provider.create_bucket(credentials, name)
        except StorjIxError as e:
            raise ValidationError("cloudsync.create_bucket", e.errmsg, e.errno)

    def list_buckets(self, credentials_id: int) -> list[dict[str, Any]]:
        credentials = self._get_credentials(credentials_id)
        if not credentials:
            raise CallError("Invalid credentials")

        provider = REMOTES[credentials.provider.type]

        if not provider.buckets:
            raise CallError("This provider does not use buckets")

        if provider.custom_list_buckets:
            return [
                {
                    "Path": bucket["name"],
                    "Name": bucket["name"],
                    "Size": -1,
                    "MimeType": "inode/directory",
                    "ModTime": bucket["time"],
                    "IsDir": True,
                    "IsBucket": True,
                    "Enabled": bucket["enabled"],
                }
                for bucket in provider.list_buckets(credentials)
            ]

        return self.ls(RcloneConfigParams(credentials=credentials), "")

    def list_directory(self, data: CloudSyncListDirectory) -> list[dict[str, Any]]:
        verrors = ValidationErrors()

        self._basic_validate(verrors, "cloud_sync", data.model_dump(by_alias=True, context={"expose_secrets": True}))

        verrors.check()

        credentials = self._get_credentials(data.credentials)
        assert credentials is not None

        path = get_remote_path(REMOTES[credentials.provider.type], data.attributes)

        return self.ls(
            RcloneConfigParams(
                credentials=credentials,
                attributes=data.attributes,
                encryption=data.encryption,
                filename_encryption=data.filename_encryption,
                encryption_password=data.encryption_password.get_secret_value(),
                encryption_salt=data.encryption_salt.get_secret_value(),
            ),
            path,
        )

    def ls(self, params: RcloneConfigParams, path: str) -> list[dict[str, Any]]:
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

        decrypt_filenames = params.encryption and params.filename_encryption
        with RcloneConfig(params) as config:
            proc = subprocess.run(["rclone", "--config", config.config_path, "lsjson", "remote:" + path],
                                  check=False, encoding="utf8", errors="ignore", capture_output=True)
            if proc.returncode == 0:
                result: list[dict[str, Any]] = json.loads(proc.stdout)

                for item in result:
                    item["Enabled"] = True

                if decrypt_filenames:
                    if result:
                        decrypted_names = {}
                        # Returns unencrypted file names when provided with a list of encrypted file
                        # names. List limit is 10 items
                        for batch in itertools.batched([item["Name"] for item in result], 10):
                            proc = subprocess.run(
                                [
                                    "rclone",
                                    "--config",
                                    config.config_path,
                                    "cryptdecode",
                                    "encrypted:",
                                    *batch
                                ],
                                check=False,
                                encoding="utf8",
                                errors="ignore",
                                capture_output=True,
                            )
                            for line in proc.stdout.splitlines():
                                try:
                                    encrypted, decrypted = line.rstrip("\r\n").split(" \t ", 1)
                                except ValueError:
                                    continue

                                if decrypted != "Failed to decrypt":
                                    decrypted_names[encrypted] = decrypted

                        for item in result:
                            if item["Name"] in decrypted_names:
                                item["Decrypted"] = decrypted_names[item["Name"]]

                return result
            else:
                raise CallError(proc.stderr, extra={"excerpt": lsjson_error_excerpt(proc.stderr)})

    def providers(self) -> list[CloudSyncProvider]:
        return sorted(
            [
                CloudSyncProvider(
                    name=provider.name,
                    title=provider.title,
                    credentials_oauth=(
                        f"{OAUTH_URL}/{(provider.credentials_oauth_name or provider.name.lower())}"
                        if provider.credentials_oauth else None
                    ),
                    buckets=provider.buckets,
                    bucket_title=provider.bucket_title,
                    task_schema=[
                        CloudSyncProviderTaskSchemaItem(property=attribute)
                        for attribute in self.task_attributes(provider)
                    ],
                )
                for provider in REMOTES.values()
            ],
            key=lambda provider: provider.title.lower()
        )

    def _build_task_from_entry(self, entry: CloudSyncEntry) -> CloudSyncTask:
        return CloudSyncTask(
            credentials=entry.credentials,
            attributes=entry.attributes,
            direction=entry.direction,
            transfer_mode=entry.transfer_mode,
            encryption=entry.encryption,
            filename_encryption=entry.filename_encryption,
            encryption_password=entry.encryption_password.get_secret_value(),
            encryption_salt=entry.encryption_salt.get_secret_value(),
            path=entry.path,
            include=list(entry.include),
            exclude=list(entry.exclude),
            args=entry.args,
            transfers=entry.transfers,
            bwlimit=[limit.model_dump() for limit in entry.bwlimit],
            snapshot=entry.snapshot,
            create_empty_src_dirs=entry.create_empty_src_dirs,
            follow_symlinks=entry.follow_symlinks,
            pre_script=entry.pre_script,
            post_script=entry.post_script,
            description=entry.description,
            id=entry.id,
        )

    def _build_task_from_payload(self, payload: dict[str, Any], credentials: Any) -> CloudSyncTask:
        return CloudSyncTask(
            credentials=credentials,
            attributes=CloudTaskAttributes(**payload["attributes"]),
            direction=payload["direction"],
            transfer_mode=payload["transfer_mode"],
            encryption=payload["encryption"],
            filename_encryption=payload["filename_encryption"],
            encryption_password=payload["encryption_password"],
            encryption_salt=payload["encryption_salt"],
            path=payload["path"],
            include=payload["include"],
            exclude=payload["exclude"],
            args=payload["args"],
            transfers=payload["transfers"],
            bwlimit=payload["bwlimit"],
            snapshot=payload["snapshot"],
            create_empty_src_dirs=payload["create_empty_src_dirs"],
            follow_symlinks=payload["follow_symlinks"],
            pre_script=payload["pre_script"],
            post_script=payload["post_script"],
            description=payload["description"],
            id=None,
        )

    def sync(self, job: Job, id_: int, options: CloudSyncSyncOptions) -> None:
        cloud_sync = self.get_instance__sync(id_)
        if cloud_sync.locked:
            self.call_sync2(self.s.cloudsync.generate_locked_alert, id_)
            raise CallError("Dataset is locked")

        self._sync(self._build_task_from_entry(cloud_sync), options, job)

    def sync_onetime(self, job: Job, data: CloudSyncCreate, options: CloudSyncSyncOptions) -> None:
        verrors = ValidationErrors()

        # Forbid unprivileged users to execute scripts as root this way.
        for k in ["pre_script", "post_script"]:
            if getattr(data, k):
                verrors.add(
                    f"cloud_sync_sync_onetime.{k}",
                    "This option may not be used for onetime cloud sync operations",
                )

        payload = data.model_dump(by_alias=True, context={"expose_secrets": True})

        self._validate(None, verrors, "cloud_sync_sync_onetime", payload)

        verrors.check()

        self._validate_folder(verrors, "cloud_sync_sync_onetime", payload)

        verrors.check()

        credentials = self._get_credentials(payload["credentials"])
        assert credentials is not None

        self._sync(self._build_task_from_payload(payload, credentials), options, job)

    def _sync(self, task: CloudSyncTask, options: CloudSyncSyncOptions, job: Job) -> None:
        local_path = task.path
        local_direction = FsLockDirection.READ if task.direction == "PUSH" else FsLockDirection.WRITE

        remote_path = get_remote_path(REMOTES[task.credentials.provider.type], task.attributes)
        remote_direction = FsLockDirection.READ if task.direction == "PULL" else FsLockDirection.WRITE

        directions = {
            FsLockDirection.READ: "reading",
            FsLockDirection.WRITE: "writing",
        }

        job.set_progress(0, f"Locking local path {local_path!r} for {directions[local_direction]}")
        with self.local_fs_lock_manager.lock(local_path, local_direction):
            job.set_progress(0, f"Locking remote path {remote_path!r} for {directions[remote_direction]}")
            with self.remote_fs_lock_manager.lock(f"{task.credentials.id}/{remote_path}", remote_direction):
                job.set_progress(0, "Starting")
                try:
                    rclone(self.middleware, job, task, options.dry_run)
                    if task.id is not None:
                        self.call_sync2(self.s.alert.oneshot_delete, "CloudSyncTaskFailed", task.id)
                except Exception:
                    if task.id is not None:
                        self.call_sync2(self.s.alert.oneshot_create, CloudSyncTaskFailedAlert(
                            id=task.id,
                            name=task.description,
                        ))
                    raise

    def abort(self, id_: int) -> bool:
        cloud_sync = self.get_instance__sync(id_)

        if cloud_sync.job is None:
            return False

        if cloud_sync.job["state"] not in ["WAITING", "RUNNING"]:
            return False

        self.middleware.call_sync("core.job_abort", cloud_sync.job["id"])
        return True

    def restore(self, id_: int, opts: RestoreOpts) -> CloudSyncEntry:
        cloud_sync = self.get_instance__sync(id_, {"retrieve_locked_info": False})

        data = {
            "description": opts.description,
            "transfer_mode": opts.transfer_mode,
            "path": opts.path,
            "direction": "PULL" if cloud_sync.direction == "PUSH" else "PUSH",
            "credentials": cloud_sync.credentials.id,
            "encryption": cloud_sync.encryption,
            "filename_encryption": cloud_sync.filename_encryption,
            "encryption_password": cloud_sync.encryption_password.get_secret_value(),
            "encryption_salt": cloud_sync.encryption_salt.get_secret_value(),
            "schedule": cloud_sync.schedule.model_dump(),
            "transfers": cloud_sync.transfers,
            "attributes": cloud_sync.attributes.model_dump(by_alias=True),
            "enabled": False,  # Do not run it automatically
        }

        entry: CloudSyncEntry = self.call_sync2(self.s.cloudsync.create, data)
        return entry
