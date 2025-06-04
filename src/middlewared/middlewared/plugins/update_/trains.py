import json

from aiohttp import ClientResponseError, ClientSession, ClientTimeout

from middlewared.service import CallError, private, Service
from middlewared.utils.network import INTERNET_TIMEOUT
from middlewared.utils.functools_ import cache
from .profile import Profile
from .utils import scale_update_server, SCALE_MANIFEST_FILE


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
        await self.middleware.call('network.general.will_perform_activity', 'update')

        async with ClientSession(**self.opts) as client:
            try:
                async with client.get(url) as resp:
                    return await resp.json()
            except ClientResponseError as e:
                raise CallError(f'Error while fetching update manifest: {e}')

    @private
    async def get_trains(self):
        """
        Returns an ordered list of currently available trains in the following format:

        ```
            {
                "trains": {
                    "TrueNAS-SCALE-Fangtooth": {
                        "description": "TrueNAS SCALE Fangtooth 25.04 [release]",
                        "update_profile": "GENERAL"
                    }
                },
                "trains_redirection": {
                    "TrueNAS-SCALE-Fangtooth-RC": "TrueNAS-SCALE-Fangtooth",
                }
            }
        ```
        """
        trains = await self.fetch(f"{self.update_srv}/trains.json")

        current_train_name = await self.get_current_train_name(trains)
        if current_train_name not in trains['trains']:
            trains['trains'][current_train_name] = {'update_profile': Profile.DEVELOPER.name}

        return trains

    @private
    async def get_train_manifest(self, name):
        return await self.fetch(f"{self.update_srv}/{name}/manifest.json")

    @private
    async def get_current_train_name(self, trains):
        manifest = await self.middleware.call('update.get_manifest_file')

        if manifest['train'] in trains['trains_redirection']:
            return trains['trains_redirection'][manifest['train']]
        else:
            return manifest['train']
