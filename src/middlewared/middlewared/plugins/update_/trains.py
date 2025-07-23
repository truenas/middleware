import json
import time

from aiohttp import ClientResponseError, ClientSession, ClientTimeout

from middlewared.service import CallError, private, Service
from middlewared.utils import MANIFEST_FILE
from middlewared.utils.network import INTERNET_TIMEOUT
from middlewared.utils.functools_ import cache
from .utils import scale_update_server


class UpdateService(Service):
    opts = {'raise_for_status': True, 'trust_env': True, 'timeout': ClientTimeout(INTERNET_TIMEOUT)}
    update_srv = scale_update_server()

    @private
    @cache
    def get_manifest_file(self):
        with open(MANIFEST_FILE) as f:
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
                        "description": "TrueNAS SCALE Fangtooth 25.04 [release]"
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
            trains['trains'][current_train_name] = {}

        return trains

    @private
    async def get_train_releases(self, name):
        return await self.fetch(f"{self.update_srv}/{name}/releases.json")

    @private
    async def get_current_train_name(self, trains):
        manifest = await self.middleware.call('update.get_manifest_file')

        if manifest['train'] in trains['trains_redirection']:
            return trains['trains_redirection'][manifest['train']]
        else:
            return manifest['train']

    @private
    async def get_next_trains_names(self, trains):
        """
        Returns the names of trains to which this system can be upgraded, listed in descending order (most recent
        train first).

        Currently, the system can be upgraded only to the next train — skipping trains is not allowed. If the next train
        does not include a version that matches the requested update profile, the current train will also be considered.
        """
        current_train_name = await self.get_current_train_name(trains)
        trains_names = list(trains['trains'].keys())
        try:
            index = trains_names.index(current_train_name)
        except ValueError:
            raise CallError(f'Current train {current_train_name!r} is not present in the update trains list') from None

        next_trains_names = []
        try:
            next_trains_names.append(trains_names[index + 1])
        except IndexError:
            # Current train is the newest train
            pass

        next_trains_names.append(current_train_name)

        return next_trains_names

    release_notes_cache = {}

    @private
    async def release_notes(self, train, filename):
        await self.middleware.call('network.general.will_perform_activity', 'update')

        for key, (release_notes, expires_at) in list(self.release_notes_cache.items()):
            if time.monotonic() > expires_at:
                self.release_notes_cache.pop(key)
                continue

        url = f"{self.update_srv}/{train}/{filename.removesuffix('.update')}.release-notes.txt"
        if url in self.release_notes_cache:
            return self.release_notes_cache[url][0]

        async with ClientSession(**self.opts) as client:
            try:
                async with client.get(url) as resp:
                    release_notes = await resp.text()
            except ClientResponseError:
                release_notes = None

        self.release_notes_cache[url] = (release_notes, time.monotonic() + 86400)
        return release_notes
