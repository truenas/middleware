import os
import shlex
import textwrap

from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.schema import Bool, Str
from middlewared.service import private
from middlewared.validators import validate_schema


class CloudTaskServiceMixin:
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
            await provider.pre_save_task(data, credentials, verrors)

        verrors.add_child(f"{name}.attributes", attributes_verrors)

    @private
    async def _validate(self, verrors, name, data):
        await self._basic_validate(verrors, name, data)

        for i, (limit1, limit2) in enumerate(zip(data["bwlimit"], data["bwlimit"][1:])):
            if limit1["time"] >= limit2["time"]:
                verrors.add(f"{name}.bwlimit.{i + 1}.time", f"Invalid time order: {limit1['time']}, {limit2['time']}")

        await self.validate_path_field(data, name, verrors)

        if data["snapshot"]:
            if await self.middleware.call("filesystem.is_cluster_path", data["path"]):
                verrors.add(f"{name}.snapshot", "This option can not be used for cluster paths")
            elif await self.middleware.call("pool.dataset.query",
                                            [["name", "^", os.path.relpath(data["path"], "/mnt") + "/"],
                                             ["type", "=", "FILESYSTEM"]]):
                verrors.add(f"{name}.snapshot", "This option is only available for datasets that have no further "
                                                "nesting")
