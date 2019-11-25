from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import item_method, Service


class CloudSyncService(Service):

    @item_method
    @accepts(
        Int("id"),
        Dict(
            "cloud_sync_restore",
            Str("description"),
            Str("transfer_mode", enum=["SYNC", "COPY"], required=True),
            Str("path", required=True),
        )
    )
    async def restore(self, id, data):
        """
        Create the opposite of cloud sync task `id` (PULL if it was PUSH and vice versa).
        """
        cloud_sync = await self.middleware.call("cloudsync.query", [["id", "=", id]], {"get": True})
        credentials = cloud_sync["credentials"]

        if cloud_sync["direction"] == "PUSH":
            data["direction"] = "PULL"
        else:
            data["direction"] = "PUSH"

        data["credentials"] = credentials["id"]

        for k in ["encryption", "filename_encryption", "encryption_password", "encryption_salt", "schedule",
                  "transfers", "attributes"]:
            data[k] = cloud_sync[k]

        data["enabled"] = False  # Do not run it automatically

        return await self.middleware.call("cloudsync.create", data)
