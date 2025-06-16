import errno
import hashlib
import itertools
import os
import time
import threading

import requests
import requests.exceptions

from middlewared.api import api_method
from middlewared.api.current import UpdateDownloadArgs, UpdateDownloadResult
from middlewared.service import CallError, job, private, Service
from middlewared.utils.size import format_size
from .utils import DOWNLOAD_UPDATE_FILE, scale_update_server, UPLOAD_LOCATION


class UpdateService(Service):

    download_update_lock = threading.Lock()

    @api_method(UpdateDownloadArgs, UpdateDownloadResult, roles=['SYSTEM_UPDATE_WRITE'])
    @job()
    def download(self, job, train, version):
        """
        Download updates.
        """
        location = self.middleware.call_sync('update.get_update_location')
        return self.download_update(job, train, version, location, 100)

    @private
    def download_update(self, job, train, version, location, progress_proportion):
        if not self.download_update_lock.acquire(False):
            raise CallError('Another update download is currently being performed.')

        try:
            self.middleware.call_sync('network.general.will_perform_activity', 'update')

            job.set_progress(0, "Retrieving update manifest")

            update_status = self.middleware.call_sync('update.status')
            if update_status['error']:
                raise CallError(f'Error retrieving update status: {update_status["error"]}')

            if train is None and version is None:
                if update_status['status']['new_version'] is None:
                    return False

                train = update_status['status']['new_version']['manifest']['train']
                version = update_status['status']['new_version']['version']
                manifest = update_status['status']['new_version']['manifest']

                if not self.middleware.call_sync('update.can_update_to', version):
                    return False
            elif train is not None and version is not None:
                if not self.middleware.call_sync('update.can_update_to', version):
                    raise CallError('Cannot update to specified version')

                manifest = self.middleware.call_sync('update.get_train_releases', train).get(version)
                if manifest is None:
                    raise CallError('Specified version does not exist')
            else:
                raise CallError('`train` and `version` must either both be `null` or both be non-`null`')

            try:
                def set_progress(progress, description):
                    job.set_progress(progress * progress_proportion, description)
                    self.middleware.call_sync('update.set_update_download_progress', {
                        'description': description,
                        'version': version,
                        'percent': progress * 100,
                    }, update_status)

                dst = os.path.join(location, DOWNLOAD_UPDATE_FILE)
                try:
                    with open(dst, "rb") as f:
                        set_progress(0, "Verifying existing update")
                        checksum = hashlib.file_digest(f, "sha256").hexdigest()
                except FileNotFoundError:
                    pass
                else:
                    if checksum == manifest["checksum"]:
                        set_progress(1, "Update downloaded.")
                        return True
                    else:
                        self.logger.warning("Invalid update file checksum %r, re-downloading", checksum)
                        os.unlink(dst)

                st = os.statvfs(location)
                avail = st.f_bavail * st.f_frsize

                # make sure we have at least as the filesize plus 500MiB
                required_size = manifest["filesize"] + 500 * 1024 ** 2
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
                                f"{scale_update_server()}/{train}/{manifest['filename']}",
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
                                        f'{format_size(progress / (time.monotonic() - download_start))}/s'
                                    )

                                    f.write(chunk)
                                break
                        except Exception as e:
                            if i < 5 and progress and any(ee in str(e) for ee in ("ECONNRESET", "ETIMEDOUT")):
                                self.middleware.logger.warning("Recoverable update download error: %r", e)
                                time.sleep(2)
                                continue

                            raise

                size = os.path.getsize(dst)
                if size != total:
                    os.unlink(dst)
                    raise CallError(f'Downloaded update file mismatch ({size} != {total})')

                set_progress(1, "Update downloaded.")
                return True
            except Exception:
                self.middleware.call_sync('update.set_update_download_progress', None, update_status)
                raise
        finally:
            self.download_update_lock.release()

    @private
    def verify_existing_update(self):
        update_status = self.middleware.call_sync('update.status')
        if update_status['status'] is None:
            return

        manifest = update_status["status"]["new_version"]["manifest"]
        dst = os.path.join(self.middleware.call_sync("update.get_update_location"), DOWNLOAD_UPDATE_FILE)
        if os.path.exists(dst) and os.path.getsize(dst) == manifest["filesize"]:
            with open(dst, "rb") as f:
                checksum = hashlib.file_digest(f, "sha256").hexdigest()

            if checksum == manifest["checksum"]:
                self.middleware.call_sync("update.set_update_download_progress", {
                    "version": manifest["version"],
                    "percent": 100,
                    "description": "Update downloaded."
                }, update_status)

    @private
    def get_update_location(self):
        syspath = self.middleware.call_sync('systemdataset.config')['path']
        if syspath:
            path = f'{syspath}/update'
        else:
            path = UPLOAD_LOCATION
        os.makedirs(path, exist_ok=True)
        return path


async def verify_existing_update(middleware, event_type, args):
    try:
        await middleware.call('update.verify_existing_update')
    except Exception:
        pass


async def setup(middleware):
    middleware.event_subscribe('system.ready', verify_existing_update)
