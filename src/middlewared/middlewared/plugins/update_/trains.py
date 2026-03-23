import errno
import json
import time

from aiohttp import ClientError, ClientConnectorError, ClientSession, ClientTimeout

from middlewared.service import CallError, private, Service
from middlewared.utils import MANIFEST_FILE, UPDATE_TRAINS_FILE_NAME
from middlewared.utils.network import INTERNET_TIMEOUT
from middlewared.utils.functools_ import cache
from .profile_ import UpdateProfiles
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
            except ClientError as e:
                # Some `aiohttp.ClientConnectorError` subclasses (i.e. `ClientConnectorCertificateError`) do not have
                # `os_error` attribute despite the parent class having one.
                if (
                    isinstance(e, ClientConnectorError) and
                    hasattr(e, 'os_error') and
                    e.os_error.errno == errno.ENETUNREACH
                ):
                    error = errno.ENETUNREACH
                else:
                    error = errno.ECONNRESET

                raise CallError(f'Error while fetching update manifest: {e}', error)
            except TimeoutError:
                raise CallError('Connection timeout while fetching update manifest', errno.ETIMEDOUT)

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
        trains = await self.fetch(f"{self.update_srv}/{UPDATE_TRAINS_FILE_NAME}")
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

        Only trains that can potentially contain a release with a configured profile level (or higher) are returned.

        Currently, the system can be upgraded to any train between the current train and the next stable train.
        Skipping stable trains is not allowed. If none of the next trains include a version that matches the requested
        update profile, the current train will also be considered.
        """
        current_train_name = await self.get_current_train_name(trains)
        trains_names = list(trains['trains'].keys())
        try:
            index = trains_names.index(current_train_name)
        except ValueError:
            raise CallError(f'Current train {current_train_name!r} is not present in the update trains list') from None

        profile = UpdateProfiles[(await self.middleware.call('update.config'))['profile']]

        next_trains_names = []
        for next_train_name in trains_names[index + 1:]:
            train = trains['trains'][next_train_name]

            try:
                train_max_profile = UpdateProfiles[train.get('max_profile', 'DEVELOPER')]
            except KeyError:
                train_max_profile = UpdateProfiles.DEVELOPER

            if train_max_profile >= profile:
                next_trains_names.append(next_train_name)

            if train.get('stable', True):
                # When a stable train is found, stop. Skipping stable trains is not allowed.
                # All trains are stable by default
                break

        # Trains came in ascending order. The result should be in descending order.
        next_trains_names = list(reversed(next_trains_names))

        next_trains_names.append(current_train_name)

        return next_trains_names

    release_notes_cache = {}

    @private
    async def release_notes(self, train, filename):
        """
        Fetch release notes from the update server.

        The release notes are cached for one day per release.
        :param train: train name
        :param filename: filename of the update file (from the release manifest)
        :return: release notes or `null` if not available.
        """
        await self.middleware.call('network.general.will_perform_activity', 'update')

        for key, (release_notes, expires_at) in list(self.release_notes_cache.items()):
            if time.monotonic() > expires_at:
                self.release_notes_cache.pop(key)

        url = f"{self.update_srv}/{train}/{filename.removesuffix('.update')}.release-notes.txt"
        if url in self.release_notes_cache:
            return self.release_notes_cache[url][0]

        async with ClientSession(**self.opts) as client:
            try:
                async with client.get(url) as resp:
                    release_notes = await resp.text()
            except Exception:
                release_notes = None

        self.release_notes_cache[url] = (release_notes, time.monotonic() + 86400)
        return release_notes
