import os
import shlex
import textwrap

from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.schema import Bool, Str
from middlewared.service import CallError, private
from middlewared.utils.privilege import credential_has_full_admin
from middlewared.validators import validate_schema


class CloudTaskServiceMixin:
    allow_zvol = False

    @private
    async def _get_credentials(self, credentials_id):
        try:
            return await self.middleware.call("datastore.query", "system.cloudcredentials",
                                              [("id", "=", credentials_id)], {"get": True})
        except IndexError:
            return None

    @private
    def _common_task_schema(self, provider):
        schema = []

        if provider.fast_list:
            schema.append(Bool("fast_list", default=False, title="Use --fast-list", description=textwrap.dedent("""\
                Use fewer transactions in exchange for more RAM. This may also speed up or slow down your
                transfer. See [rclone documentation](https://rclone.org/docs/#fast-list) for more details.
            """).rstrip()))

        return schema

    @private
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

        provider = REMOTES[credentials["provider"]]

        schema = []

        if provider.buckets:
            schema.append(Str("bucket", required=True, empty=False))

        schema.append(Str("folder", required=True))

        schema.extend(provider.task_schema)

        schema.extend(self._common_task_schema(provider))

        attributes_verrors = validate_schema(schema, data["attributes"])

        if not attributes_verrors:
            await provider.validate_task_basic(data, credentials, verrors)

        verrors.add_child(f"{name}.attributes", attributes_verrors)

    @private
    async def _validate(self, app, verrors, name, data):
        await self._basic_validate(verrors, name, data)

        if not verrors:
            credentials = await self._get_credentials(data["credentials"])

            provider = REMOTES[credentials["provider"]]

            await provider.validate_task_full(data, credentials, verrors)

        for i, (limit1, limit2) in enumerate(zip(data["bwlimit"], data["bwlimit"][1:])):
            if limit1["time"] >= limit2["time"]:
                verrors.add(f"{name}.bwlimit.{i + 1}.time", f"Invalid time order: {limit1['time']}, {limit2['time']}")

        if self.allow_zvol and (path := await self.get_path_field(data)).startswith("/dev/zvol/"):
            zvol = zvol_path_to_name(path)
            if not await self.middleware.call('pool.dataset.query', [['name', '=', zvol], ['type', '=', 'VOLUME']]):
                verrors.add(f'{name}.{self.path_field}', 'Volume does not exist')
            else:
                try:
                    await self.middleware.call(f'{self._config.namespace}.validate_zvol', path)
                except CallError as e:
                    verrors.add(f'{name}.{self.path_field}', e.errmsg)
        else:
            await self.validate_path_field(data, name, verrors)

        if data["snapshot"]:
            if await self.middleware.call("pool.dataset.query",
                                            [["name", "^", os.path.relpath(data["path"], "/mnt") + "/"],
                                             ["type", "=", "FILESYSTEM"]]):
                verrors.add(f"{name}.snapshot", "This option is only available for datasets that have no further "
                                                "nesting")

        if app and not credential_has_full_admin(app.authenticated_credentials):
            for k in ["pre_script", "post_script"]:
                if data[k]:
                    verrors.add(f"{name}.{k}", "The ability to edit cloud sync pre and post scripts is limited to "
                                               "users who have full administrative credentials")
