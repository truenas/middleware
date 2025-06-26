from middlewared.api import api_method
from middlewared.api.current import (
    CloudSyncRestoreArgs,
    CloudSyncRestoreResult,
)
from middlewared.service import Service


class CloudSyncService(Service):

    @api_method(
        CloudSyncRestoreArgs,
        CloudSyncRestoreResult,
        roles=["CLOUD_SYNC_WRITE"],
    )
    async def restore(self, id_, data):
        """
        Create the opposite of cloud sync task `id` (PULL if it was PUSH and vice versa).
        """
        cloud_sync = await self.middleware.call(
            "cloudsync.query", [["id", "=", id_]], {"get": True, "extra": {"retrieve_locked_info": False}}
        )
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
