import json

from aiohttp import ClientSession, ClientTimeout

from middlewared.service import private, Service
from middlewared.utils.network import INTERNET_TIMEOUT
from middlewared.utils.functools import cache
from .utils import can_update, scale_update_server, SCALE_MANIFEST_FILE


class UpdateService(Service):
    opts = {'raise_for_status': True, 'trust_env': True, 'timeout': ClientTimeout(INTERNET_TIMEOUT)}
    update_srv = scale_update_server()

    @private
    @cache
    def get_manifest_file(self):
        with open(SCALE_MANIFEST_FILE) as f:
            return json.load(f)

    @private
    async def fetch(self, url):
        async with ClientSession(**self.opts) as client:
            async with client.get(url) as resp:
                return await resp.json()

    @private
    async def get_scale_update(self, train, current_version):
        new_manifest = await self.fetch(f"{self.update_srv}/{train}/manifest.json")
        if not can_update(current_version, new_manifest["version"]):
            return {"status": "UNAVAILABLE"}

        return {
            "status": "AVAILABLE",
            "changes": [{
                "operation": "upgrade",
                "old": {
                    "name": "TrueNAS",
                    "version": current_version,
                },
                "new": {
                    "name": "TrueNAS",
                    "version": new_manifest["version"],
                }
            }],
            "notice": None,
            "notes": None,
            "changelog": new_manifest["changelog"],
            "version": new_manifest["version"],
            "filename": new_manifest["filename"],
            "checksum": new_manifest["checksum"],
        }

    @private
    async def get_trains_data(self):
        return {
            "current_train": (await self.middleware.call("update.get_manifest_file"))["train"],
            **(await self.fetch(f"{self.update_srv}/trains.json"))
        }

    @private
    async def check_train(self, train):
        old_vers = (await self.middleware.call("update.get_manifest_file"))["version"]
        return await self.middleware.call("update.get_scale_update", train, old_vers)
