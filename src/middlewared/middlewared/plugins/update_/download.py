from __future__ import annotations

import errno
import hashlib
import itertools
import os
import time
import threading
import typing

import requests
import requests.exceptions

from middlewared.api.current import UpdateDownloadProgress
from middlewared.service import CallError, ServiceContext
from middlewared.utils.size import format_size
from .trains import Release
from .utils import DOWNLOAD_UPDATE_FILE, scale_update_server, UPLOAD_LOCATION
from .status import status, status_internal, set_update_download_progress
from .version import can_update_to
from .trains import get_train_releases

if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


# Module-level state
_download_update_lock = threading.Lock()


def download(context: ServiceContext, job: Job, train: str | None, version: str | None) -> bool:
    location = get_update_location(context)
    return download_update(context, job, train, version, location, 100)


def download_update(
    context: ServiceContext,
    job: Job,
    train: str | None,
    version: str | None,
    location: str,
    progress_proportion: float,
) -> bool:
    if not _download_update_lock.acquire(False):
        raise CallError('Another update download is currently being performed.')

    try:
        context.middleware.call_sync('network.general.will_perform_activity', 'update')

        job.set_progress(0, "Retrieving update manifest")

        update_status = context.run_coroutine(status_internal(context, True))

        if train is None and version is None:
            if update_status.status is None or update_status.status.new_version is None:
                return False

            train = update_status.status.new_version.manifest["train"]
            version = update_status.status.new_version.version
            manifest = Release.model_validate(update_status.status.new_version.manifest)

            if not context.run_coroutine(can_update_to(context, version)):
                return False
        elif train is not None and version is not None:
            if not context.run_coroutine(can_update_to(context, version)):
                raise CallError('Cannot update to specified version')

            if probe_manifest := context.run_coroutine(get_train_releases(context, train)).get(version):
                manifest = probe_manifest
            else:
                raise CallError('Specified version does not exist')
        else:
            raise CallError('`train` and `version` must either both be `null` or both be non-`null`')

        try:
            def set_progress(progress: float, description: str) -> None:
                job.set_progress(progress * progress_proportion, description)
                context.run_coroutine(set_update_download_progress(context, UpdateDownloadProgress(
                    description=description,
                    version=version,
                    percent=progress * 100,
                ), update_status))

            dst = os.path.join(location, DOWNLOAD_UPDATE_FILE)
            try:
                with open(dst, "rb") as fr:
                    set_progress(0, "Verifying existing update")
                    checksum = hashlib.file_digest(fr, "sha256").hexdigest()
            except FileNotFoundError:
                pass
            else:
                if checksum == manifest.checksum:
                    set_progress(1, "Update downloaded.")
                    return True
                else:
                    context.logger.warning("Invalid update file checksum %r, re-downloading", checksum)
                    os.unlink(dst)

            st = os.statvfs(location)
            avail = st.f_bavail * st.f_frsize

            # make sure we have at least as the filesize plus 500MiB
            required_size = manifest.filesize + 500 * 1024 ** 2
            if required_size > avail:
                raise CallError(
                    f"{location}: insufficient available space: {format_size(avail)}, "
                    f"required: {format_size(required_size)}", errno.ENOSPC
                )

            for i in itertools.count(1):
                with open(dst, "ab") as f:
                    download_start = time.monotonic()
                    progress = None
                    try:
                        start = os.path.getsize(dst)
                        with requests.get(
                            f"{scale_update_server()}/{train}/{manifest.filename}",
                            stream=True,
                            timeout=30,
                            headers={"Range": f"bytes={start}-"}
                        ) as r:
                            r.raise_for_status()
                            total = start + int(r.headers["Content-Length"])
                            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                                progress = f.tell()

                                set_progress(
                                    progress / total,
                                    f'Downloading update: {format_size(total)} at '
                                    f'{format_size(int(progress / (time.monotonic() - download_start)))}/s'
                                )

                                f.write(chunk)

                            size = os.path.getsize(dst)
                            if size != total:
                                raise CallError(f'Downloaded update file size mismatch ({size} != {total})',
                                                errno.ECONNRESET)

                            break
                    except Exception as e:
                        if i < 5 and progress and isinstance(e, (
                            requests.exceptions.ConnectionError,
                            requests.exceptions.Timeout,
                        )):
                            context.middleware.logger.warning("Recoverable update download error: %r", e)
                            time.sleep(2)
                            continue

                        if isinstance(e, CallError):
                            raise
                        else:
                            raise CallError(f'Error downloading update: {e}', errno.ECONNRESET)

            size = os.path.getsize(dst)
            if size != total:
                os.unlink(dst)
                raise CallError(f'Downloaded update file size mismatch ({size} != {total})', errno.ECONNRESET)

            set_progress(1, "Update downloaded.")
            return True
        except Exception:
            context.run_coroutine(set_update_download_progress(context, None, update_status))
            raise
    finally:
        _download_update_lock.release()


def verify_existing_update(context: ServiceContext) -> None:
    update_status = context.run_coroutine(status(context))
    if update_status.status is None:
        return

    assert update_status.status.new_version
    manifest = update_status.status.new_version.manifest
    dst = os.path.join(get_update_location(context), DOWNLOAD_UPDATE_FILE)
    if os.path.exists(dst) and os.path.getsize(dst) == manifest["filesize"]:
        with open(dst, "rb") as f:
            checksum = hashlib.file_digest(f, "sha256").hexdigest()

        if checksum == manifest["checksum"]:
            context.run_coroutine(set_update_download_progress(context, UpdateDownloadProgress(
                version=manifest["version"],
                percent=100,
                description="Update downloaded."
            ), update_status))


def get_update_location(context: ServiceContext) -> str:
    syspath = context.middleware.call_sync('systemdataset.config')['path']
    if syspath:
        path = f'{syspath}/update'
    else:
        path = UPLOAD_LOCATION
    os.makedirs(path, exist_ok=True)
    return path


async def verify_existing_update_hook(middleware: Middleware, event_type: str, args: typing.Any) -> None:
    try:
        await middleware.call2(middleware.services.update.verify_existing_update)
    except Exception:
        pass


async def setup(middleware: Middleware) -> None:
    middleware.event_subscribe('system.ready', verify_existing_update_hook)
