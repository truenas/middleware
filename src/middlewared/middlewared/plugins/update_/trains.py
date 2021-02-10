# -*- coding=utf-8 -*-
import aiohttp
import async_timeout

from middlewared.service import private, Service
from middlewared.utils.network import INTERNET_TIMEOUT

from .utils import scale_update_server


class UpdateService(Service):
    @private
    async def get_scale_trains_data(self):
        async with async_timeout.timeout(INTERNET_TIMEOUT):
            async with aiohttp.ClientSession(
                raise_for_status=True, trust_env=True,
            ) as session:
                trains = await (await session.get(f"{scale_update_server()}/trains.json")).json()

        return trains

    @private
    async def get_scale_update(self, train, current_version):
        async with async_timeout.timeout(INTERNET_TIMEOUT):
            async with aiohttp.ClientSession(
                raise_for_status=True, trust_env=True,
            ) as session:
                new_manifest = await (await session.get(f"{scale_update_server()}/{train}/manifest.json")).json()

        if new_manifest["version"] == current_version:
            return {"status": "UNAVAILABLE"}

        return {
            "status": "AVAILABLE",
            "changes": [
                {
                    "operation": "upgrade",
                    "old": {
                        "name": "TrueNAS",
                        "version": current_version,
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
