from __future__ import annotations

import errno
import time
from typing import Any

from aiohttp import ClientError, ClientConnectorError, ClientSession, ClientTimeout
from pydantic import BaseModel

from middlewared.service import CallError, ServiceContext
from middlewared.utils import MANIFEST_FILE, UPDATE_TRAINS_FILE_NAME
from middlewared.utils.network import INTERNET_TIMEOUT
from functools import cache
from .utils import scale_update_server


class UpdateManifest(BaseModel):
    buildtime: int
    train: str
    codename: str
    version: str


class TrainDescription(BaseModel):
    description: str = ""


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
_update_srv = scale_update_server()
_release_notes_cache: dict[str, tuple[str | None, float]] = {}


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
            if isinstance(e, ClientConnectorError) and e.os_error.errno == errno.ENETUNREACH:
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
    trains = Trains.model_validate(await fetch(context, f"{_update_srv}/{UPDATE_TRAINS_FILE_NAME}"))
    current_train_name = await get_current_train_name(context, trains)
    if current_train_name not in trains.trains:
        trains.trains[current_train_name] = TrainDescription()

    return trains


async def get_train_releases(context: ServiceContext, name: str) -> dict[str, Release]:
    return {
        k: Release.model_validate(v)
        for k, v in (await fetch(context, f"{_update_srv}/{name}/releases.json")).items()
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

    Currently, the system can be upgraded only to the next train — skipping trains is not allowed. If the next train
    does not include a version that matches the requested update profile, the current train will also be considered.
    """
    current_train_name = await get_current_train_name(context, trains)
    trains_names = list(trains.trains.keys())
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

    url = f"{_update_srv}/{train}/{filename.removesuffix('.update')}.release-notes.txt"
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
