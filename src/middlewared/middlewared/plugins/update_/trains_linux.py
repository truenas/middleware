# -*- coding=utf-8 -*-
import json

import aiohttp
import async_timeout

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

        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession(
                raise_for_status=True, trust_env=True,
            ) as session:
                trains = await (await session.get(f"{scale_update_server()}/trains.json")).json()

        return {
            "current_train": manifest["train"],
            **trains,
        }

    @private
    async def check_train(self, train):
        with open(SCALE_MANIFEST_FILE) as f:
            old_manifest = json.load(f)

        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession(
                raise_for_status=True, trust_env=True,
            ) as session:
                new_manifest = await (await session.get(f"{scale_update_server()}/{train}/manifest.json")).json()

        if old_manifest["version"] == new_manifest["version"]:
            return {"status": "UNAVAILABLE"}

        return {
            "status": "AVAILABLE",
            "changes": [
                {
                    "operation": "upgrade",
                    "old": {
                        "name": "TrueNAS",
                        "version": old_manifest["version"],
                    },
                    "new": {
                        "name": "TrueNAS",
                        "version": new_manifest["version"],
                    }
                }
            ],
            "notice": None,
            "notes": None,
            "changelog": new_manifest["changelog"],
            "version": new_manifest["version"],
            "filename": new_manifest["filename"],
            "checksum": new_manifest["checksum"],
        }
