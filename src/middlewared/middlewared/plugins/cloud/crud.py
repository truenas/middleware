from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Any

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.model import model_subset
from middlewared.api.current import CloudTaskAttributes, CredentialsEntry, ZFSResourceQuery
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.rclone.base import BaseRcloneRemote
from middlewared.service import CallError, ServiceContext, private
from middlewared.service_exception import InstanceNotFound, ValidationErrors
from middlewared.utils.privilege import credential_has_full_admin

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App


class CloudTaskServiceMixin(ServiceContext):
    """Shared create/update validation for the cloud_sync and cloud_backup task services.

    ``data`` is the datastore-bound payload dict (the create/update model dumped by the leaf part); path
    validation writes the resolved ``dataset``/``relative_path`` back into it. Credentials resolve to a typed
    :class:`CredentialsEntry` and the rclone provider is called with typed models.
    """

    allow_zvol = False

    if TYPE_CHECKING:
        # Provided by the ``SharingTaskServicePart`` this mixin is combined with.
        path_field: str

        async def get_path_field(self, data: Any) -> Any: ...

        async def validate_path_field(
            self, data: dict[str, Any], schema: str, verrors: ValidationErrors, *, split_path: bool = ...,
        ) -> ValidationErrors: ...

    def _get_credentials(self, credentials: int | CredentialsEntry) -> CredentialsEntry | None:
        cred_id = credentials if isinstance(credentials, int) else credentials.id
        try:
            return self.call_sync2(self.s.cloudsync.credentials.get_instance, cred_id)
        except InstanceNotFound:
            return None

    @private
    def task_attributes(self, provider: BaseRcloneRemote) -> list[str]:
        attributes = []

        if provider.buckets:
            attributes.append("bucket")

        attributes.append("folder")

        if provider.fast_list:
            attributes.append("fast_list")

        attributes += provider.task_attributes

        return attributes

    def _basic_validate(self, verrors: ValidationErrors, name: str, data: dict[str, Any]) -> None:
        try:
            shlex.split(data["args"])
        except ValueError as e:
            verrors.add(f"{name}.args", f"Parse error: {e.args[0]}")

        credentials = self._get_credentials(data["credentials"])
        if not credentials:
            verrors.add(f"{name}.credentials", "Invalid credentials")

        if verrors:
            return

        provider = REMOTES[credentials.provider.type]

        try:
            data["attributes"] = validate_model(
                model_subset(CloudTaskAttributes, self.task_attributes(provider)),
                data["attributes"],
            )
        except ValidationErrors as e:
            verrors.add_child(f"{name}.attributes", e)
        else:
            attributes = CloudTaskAttributes(**data["attributes"])
            provider.validate_task_basic(attributes, credentials, verrors)
            # `validate_task_basic` may normalize the attributes (e.g. S3 fills in the bucket region).
            data["attributes"] = attributes.model_dump(by_alias=True, exclude_unset=True)

    def _validate(self, app: App | None, verrors: ValidationErrors, name: str, data: dict[str, Any]) -> None:
        self._basic_validate(verrors, name, data)

        if not verrors:
            credentials = self._get_credentials(data["credentials"])
            assert credentials is not None

            provider = REMOTES[credentials.provider.type]

            provider.validate_task_full(CloudTaskAttributes(**data["attributes"]), credentials, verrors)

        if self.allow_zvol and (
            path := self.middleware.run_coroutine(self.get_path_field(data))
        ).startswith("/dev/zvol/"):
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
            self.middleware.run_coroutine(self.validate_path_field(data, name, verrors, split_path=True))

        if data["snapshot"]:
            dataset_name = data["path"].removeprefix("/mnt/")
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

        if app and not credential_has_full_admin(app.authenticated_credentials):
            for k in ["pre_script", "post_script"]:
                if data[k]:
                    verrors.add(f"{name}.{k}", "The ability to edit pre-scripts and post-scripts is limited to "
                                               "users who have full administrative credentials")
