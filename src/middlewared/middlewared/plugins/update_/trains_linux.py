# -*- coding=utf-8 -*-
import json

from middlewared.service import private, Service

from .utils import SCALE_MANIFEST_FILE, scale_update_server


class UpdateService(Service):
    @private
    async def get_trains_redirection_url(self):
        return f"{scale_update_server()}/trains_redir.json"

    @private
    async def get_trains_data(self):
        with open(SCALE_MANIFEST_FILE) as f:
            manifest = json.load(f)

        trains = await self.middleware.call("update.get_scale_trains_data")

        return {
            "current_train": manifest["train"],
            **trains,
        }

    @private
    async def check_train(self, train):
        with open(SCALE_MANIFEST_FILE) as f:
            old_manifest = json.load(f)

        return await self.middleware.call("update.get_scale_update", train, old_manifest["version"])
