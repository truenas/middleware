import shlex

from middlewared.api.base.handler.accept import validate_model
from middlewared.api.base.model import model_subset
from middlewared.api.current import CloudTaskAttributes, ZFSResourceQuery
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.service import CallError, private
from middlewared.service_exception import InstanceNotFound, ValidationErrors
from middlewared.utils.privilege import credential_has_full_admin


class CloudTaskServiceMixin:
    allow_zvol = False

    async def _get_credentials(self, credentials_id):
        try:
            return await self.middleware.call("cloudsync.credentials.get_instance", credentials_id)
        except InstanceNotFound:
            return None

    @private
    def task_attributes(self, provider):
        attributes = []

        if provider.buckets:
            attributes.append("bucket")

        attributes.append("folder")

        if provider.fast_list:
            attributes.append("fast_list")

        attributes += provider.task_attributes

        return attributes

    async def _basic_validate(self, verrors, name, data):
        try:
            shlex.split(data["args"])
        except ValueError as e:
            verrors.add(f"{name}.args", f"Parse error: {e.args[0]}")

        credentials = await self._get_credentials(data["credentials"])
        if not credentials:
            verrors.add(f"{name}.credentials", "Invalid credentials")

        if verrors:
            return

        provider = REMOTES[credentials["provider"]["type"]]

        try:
            data["attributes"] = validate_model(
                model_subset(CloudTaskAttributes, self.task_attributes(provider)),
                data["attributes"],
            )
        except ValidationErrors as e:
            verrors.add_child(f"{name}.attributes", e)
        else:
            await provider.validate_task_basic(data, credentials, verrors)

    async def _validate(self, app, verrors, name, data):
        await self._basic_validate(verrors, name, data)

        if not verrors:
            credentials = await self._get_credentials(data["credentials"])

            provider = REMOTES[credentials["provider"]["type"]]

            await provider.validate_task_full(data, credentials, verrors)

        if self.allow_zvol and (path := await self.get_path_field(data)).startswith("/dev/zvol/"):
            zvol = zvol_path_to_name(path)
            zz = await self.call2(self.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[zvol], properties=None))
            if not zz:
                verrors.add(f'{name}.{self.path_field}', 'Volume does not exist')
            elif not zz[0]['type'] == 'VOLUME':
                verrors.add(f'{name}.{self.path_field}', f'{zvol!r} is not a volume')
            elif has_internal_path(zz[0]['name']):
                verrors.add(f'{name}.{self.path_field}', f'{zvol!r} is an invalid location')
            else:
                try:
                    await self.middleware.call(f'{self._config.namespace}.validate_zvol', path)
                except CallError as e:
                    verrors.add(f'{name}.{self.path_field}', e.errmsg)
        else:
            await self.validate_path_field(data, name, verrors)

        if data["snapshot"]:
            for i in await self.call2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(
                    paths=[data["path"].removeprefix("/mnt/")],
                    properties=None,
                    get_children=True
                ),
            ):
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
