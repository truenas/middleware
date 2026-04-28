from __future__ import annotations

import errno
from functools import cache
import time
from typing import Any

from aiohttp import ClientError, ClientConnectorError, ClientSession, ClientTimeout
from pydantic import BaseModel

from middlewared.service import CallError, ServiceContext
from middlewared.utils import MANIFEST_FILE, UPDATE_TRAINS_FILE_NAME
from middlewared.utils.network import INTERNET_TIMEOUT
from middlewared.plugins.update_ import profile_
from .utils import scale_update_server


class UpdateManifest(BaseModel):
    buildtime: int
    train: str
    version: str


class TrainDescription(BaseModel):
    # Human-readable train description.
    description: str = ""
    # Whether this train is a stable release. The system can be upgraded to any train
    # between the current train and the next stable train. Skipping stable trains is
    # not allowed. This must be `True` for stable releases and `False` for Nightly,
    # Alpha, Beta, RC, and other pre-release versions.
    stable: bool = True
    # The highest release profile included in the train's release files.
    max_profile: str = "DEVELOPER"


class Trains(BaseModel):
    trains: dict[str, TrainDescription]
    trains_redirection: dict[str, str] = {}


class Release(BaseModel):
    filename: str
    version: str
    date: str
    changelog: str
    checksum: str
    filesize: int
    profile: str


class ReleaseManifest(Release):
    train: str


# Module-level configuration
_opts = {'raise_for_status': True, 'trust_env': True, 'timeout': ClientTimeout(INTERNET_TIMEOUT)}
_release_notes_cache: dict[str, tuple[str | None, float]] = {}


async def get_update_server(context: ServiceContext) -> str:
    cfg = await context.call2(context.s.update.config_safe)
    return scale_update_server(lts=cfg.lts)


@cache
def get_manifest_file() -> UpdateManifest:
    with open(MANIFEST_FILE) as f:
        return UpdateManifest.model_validate_json(f.read())


async def fetch(context: ServiceContext, url: str) -> Any:
    await context.middleware.call('network.general.will_perform_activity', 'update')

    async with ClientSession(**_opts) as client:  # type: ignore
        try:
            async with client.get(url) as resp:
                return await resp.json()
        except ClientError as e:
            # Some `aiohttp.ClientConnectorError` subclasses (i.e. `ClientConnectorCertificateError`) do not have
            # `os_error` attribute despite the parent class having one.
            if isinstance(e, ClientConnectorError) and hasattr(e, 'os_error') and e.os_error.errno == errno.ENETUNREACH:
                error = errno.ENETUNREACH
            else:
                error = errno.ECONNRESET

            raise CallError(f'Error while fetching update manifest: {e}', error)
        except TimeoutError:
            raise CallError('Connection timeout while fetching update manifest', errno.ETIMEDOUT)


async def get_trains(context: ServiceContext) -> Trains:
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
    update_srv = await get_update_server(context)
    trains = Trains.model_validate(await fetch(context, f"{update_srv}/{UPDATE_TRAINS_FILE_NAME}"))
    current_train_name = await get_current_train_name(context, trains)
    if current_train_name not in trains.trains:
        trains.trains[current_train_name] = TrainDescription()

    return trains


async def get_train_releases(context: ServiceContext, name: str) -> dict[str, Release]:
    update_srv = await get_update_server(context)
    return {
        k: Release.model_validate(v)
        for k, v in (await fetch(context, f"{update_srv}/{name}/releases.json")).items()
    }


async def get_current_train_name(context: ServiceContext, trains: Trains) -> str:
    manifest = get_manifest_file()

    if manifest.train in trains.trains_redirection:
        return trains.trains_redirection[manifest.train]
    else:
        return manifest.train


async def get_next_trains_names(context: ServiceContext, trains: Trains) -> list[str]:
    """
    Returns the names of trains to which this system can be upgraded, listed in descending order (most recent
    train first).

    Only trains that can potentially contain a release with a configured profile level (or higher) are returned.

    Currently, the system can be upgraded to any train between the current train and the next stable train.
    Skipping stable trains is not allowed. If none of the next trains include a version that matches the requested
    update profile, the current train will also be considered.
    """
    current_train_name = await get_current_train_name(context, trains)
    trains_names = list(trains.trains.keys())
    try:
        index = trains_names.index(current_train_name)
    except ValueError:
        raise CallError(f'Current train {current_train_name!r} is not present in the update trains list') from None

    profile = profile_.UpdateProfiles[(await context.call2(context.s.update.config)).profile]

    next_trains_names = []
    for next_train_name in trains_names[index + 1:]:
        train = trains.trains[next_train_name]

        try:
            train_max_profile = profile_.UpdateProfiles[train.max_profile]
        except KeyError:
            train_max_profile = profile_.UpdateProfiles.DEVELOPER

        if train_max_profile >= profile:
            next_trains_names.append(next_train_name)

        if train.stable:
            # When a stable train is found, stop. Skipping stable trains is not allowed.
            # All trains are stable by default
            break

    # Trains came in ascending order. The result should be in descending order.
    next_trains_names = list(reversed(next_trains_names))

    next_trains_names.append(current_train_name)

    return next_trains_names


async def release_notes(context: ServiceContext, train: str, filename: str) -> str | None:
    """
    Fetch release notes from the update server.

    The release notes are cached for one day per release.
    :param train: train name
    :param filename: filename of the update file (from the release manifest)
    :return: release notes or `null` if not available.
    """
    await context.middleware.call('network.general.will_perform_activity', 'update')

    for key, (notes, expires_at) in list(_release_notes_cache.items()):
        if time.monotonic() > expires_at:
            _release_notes_cache.pop(key)

    update_srv = await get_update_server(context)
    url = f"{update_srv}/{train}/{filename.removesuffix('.update')}.release-notes.txt"
    if url in _release_notes_cache:
        return _release_notes_cache[url][0]

    async with ClientSession(**_opts) as client:  # type: ignore
        try:
            async with client.get(url) as resp:
                release_notes_text = await resp.text()
        except Exception:
            release_notes_text = None

    _release_notes_cache[url] = (release_notes_text, time.monotonic() + 86400)
    return release_notes_text
