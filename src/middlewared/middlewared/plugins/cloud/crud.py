from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Any, Protocol, Self

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.model import model_subset
from middlewared.api.current import CloudTaskAttributes, CredentialsEntry, ZFSResourceQuery
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.service import CallError, SharingTaskServicePart
from middlewared.service_exception import InstanceNotFound, ValidationErrors
from middlewared.utils.privilege import credential_has_full_admin

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel
    from middlewared.api.base.server.app import App


def task_attributes[T: BaseModel](remote: BaseRcloneRemote[T]) -> list[str]:
    attributes = []

    if remote.buckets:
        attributes.append("bucket")

    attributes.append("folder")

    if remote.fast_list:
        attributes.append("fast_list")

    attributes += remote.task_attributes

    return attributes


def validate_task_attributes[T: BaseModel](
    remote: BaseRcloneRemote[T],
    attributes: dict[str, Any],
) -> CloudTaskAttributes:
    return validate_model(  # type: ignore[return-value]
        model_subset(CloudTaskAttributes, task_attributes(remote)),
        attributes,
        dump_models=False,
    )


class HasCredentials(Protocol):
    @property
    def credentials(self) -> int | CredentialsEntry: ...


class RunnableCloudTask(HasCredentials, Protocol):
    args: str
    attributes: CloudTaskAttributes


class CloudTaskBase(Protocol):
    args: str
    attributes: CloudTaskAttributes
    dataset: Any
    relative_path: Any
    snapshot: bool
    path: str
    pre_script: str
    post_script: str

    def model_dump(self, *, expose_secrets: bool = ...) -> dict[str, Any]: ...


class CloudTaskEntry(CloudTaskBase, Protocol):
    id: int

    @property
    def credentials(self) -> CredentialsEntry: ...

    def updated(self, value: Any) -> Self: ...


class CloudTaskCreate(CloudTaskBase, Protocol):
    @property
    def credentials(self) -> int: ...


class CloudTaskUpdate(CloudTaskCreate, Protocol):
    pass


class CloudTaskServiceMixin[
    EntryT: CloudTaskEntry,
    CreateT: CloudTaskCreate,
    UpdateT: CloudTaskUpdate,
](SharingTaskServicePart[EntryT]):
    __slots__ = ()

    allow_zvol = False
    schema_prefix: str

    async def do_create(self, app: App | None, data: CreateT) -> EntryT:
        compressed = await self.to_thread(self._validate_and_compress, app, f"{self.schema_prefix}_create", data)
        entry = await self._create(compressed)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_update(self, app: App | None, id_: int, data: UpdateT) -> EntryT:
        old = await self.get_instance(id_)
        new = old.updated(data)
        compressed = await self.to_thread(self._validate_and_compress, app, f"{self.schema_prefix}_update", new)
        entry = await self._update(id_, compressed)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)
        return entry

    async def do_delete(self, id_: int) -> None:
        await self._pre_delete(id_)
        await self._delete(id_)
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)

    async def _pre_delete(self, id_: int) -> None:
        raise NotImplementedError

    def _validate_and_compress(self, app: App | None, schema: str, entry: EntryT | CreateT) -> dict[str, Any]:
        verrors = ValidationErrors()
        self._validate(app, verrors, schema, entry)
        verrors.check()

        data = entry.model_dump(expose_secrets=True)
        data["dataset"] = entry.dataset
        data["relative_path"] = entry.relative_path
        data.pop(self.locked_field, None)
        data.pop("job", None)
        if isinstance(data["credentials"], dict):
            data["credentials"] = data["credentials"]["id"]

        return data

    def _credential_id(self, entry: HasCredentials) -> int:
        return entry.credentials if isinstance(entry.credentials, int) else entry.credentials.id

    def _get_credentials(self, credentials_id: int) -> CredentialsEntry | None:
        try:
            return self.call_sync2(self.s.cloudsync.credentials.get_instance, credentials_id)
        except InstanceNotFound:
            return None

    def _basic_validate(self, verrors: ValidationErrors, name: str, entry: EntryT | CreateT) -> None:
        try:
            shlex.split(entry.args)
        except ValueError as e:
            verrors.add(f"{name}.args", f"Parse error: {e.args[0]}")
            return

        credentials = self._get_credentials(self._credential_id(entry))
        if not credentials:
            verrors.add(f"{name}.credentials", "Invalid credentials")
            return

        remote = REMOTES[credentials.provider.type]

        try:
            attributes = validate_task_attributes(remote, entry.attributes.model_dump(expose_secrets=True))
        except ValidationErrors as e:
            verrors.add_child(f"{name}.attributes", e)
        else:
            remote.validate_task_basic(attributes, credentials.provider, verrors)
            entry.attributes = attributes

    def _validate(self, app: App | None, verrors: ValidationErrors, name: str, entry: EntryT | CreateT) -> None:
        self._basic_validate(verrors, name, entry)

        if not verrors:
            credentials = self._get_credentials(self._credential_id(entry))
            assert credentials is not None

            remote = REMOTES[credentials.provider.type]

            remote.validate_task_full(entry.attributes, credentials.provider, verrors)

        if self.allow_zvol and (
            path := self.middleware.run_coroutine(self.get_path_field(entry))  # type: ignore[arg-type]
        ).startswith("/dev/zvol/"):
            entry.dataset = None
            entry.relative_path = None
            zvol = zvol_path_to_name(path)
            zz = self.call_sync2(self.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[zvol], properties=None))
            if not zz:
                verrors.add(f'{name}.{self.path_field}', 'Volume does not exist')
            elif not zz[0]['type'] == 'VOLUME':
                verrors.add(f'{name}.{self.path_field}', f'{zvol!r} is not a volume')
            elif has_internal_path(zz[0]['name']):
                verrors.add(f'{name}.{self.path_field}', f'{zvol!r} is an invalid location')
            else:
                try:
                    self.call_sync2(self.s.cloud_backup.validate_zvol, path)
                except CallError as e:
                    verrors.add(f'{name}.{self.path_field}', e.errmsg)
        else:
            path_data: dict[str, Any] = {self.path_field: entry.path}
            self.middleware.run_coroutine(
                self.validate_path_field(path_data, name, verrors, split_path=True)
            )
            entry.dataset = path_data.get("dataset")
            entry.relative_path = path_data.get("relative_path")

        if entry.snapshot:
            dataset_name = entry.path.removeprefix("/mnt/")
            for i in self.call_sync2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(
                    paths=[dataset_name],
                    properties=None,
                    get_children=True
                ),
            ):
                if i["name"] == dataset_name:
                    continue

                if i["type"] == "FILESYSTEM":
                    verrors.add(
                        f"{name}.snapshot",
                        "This option is only available for datasets that have no further nesting"
                    )
                    break

        if app and not (app.authenticated_credentials and credential_has_full_admin(app.authenticated_credentials)):
            for k in ["pre_script", "post_script"]:
                if getattr(entry, k):
                    verrors.add(f"{name}.{k}", "The ability to edit pre-scripts and post-scripts is limited to "
                                               "users who have full administrative credentials")
