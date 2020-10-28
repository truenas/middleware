# -*- coding=utf-8 -*-
import itertools
import os
import subprocess
import time

import humanfriendly
import requests
import requests.exceptions

from middlewared.service import CallError, private, Service
from middlewared.utils import osc

from .utils import scale_update_server


class UpdateService(Service):
    @private
    def download_impl_scale(self, job, train, location, progress_proportion):
        job.set_progress(0, "Retrieving update manifest")

        train_check = self.middleware.call_sync("update.check_train", train)
        if train_check["status"] == "AVAILABLE":
            dst = os.path.join(location, "update.sqsh")
            if os.path.exists(dst):
                job.set_progress(0, "Verifying existing update")
                if osc.IS_FREEBSD:
                    checksum = subprocess.run(
                        ["sha256", dst], stdout=subprocess.PIPE, encoding="utf-8"
                    ).stdout.split()[-1]
                else:
                    checksum = subprocess.run(
                        ["sha256sum", dst], stdout=subprocess.PIPE, encoding="utf-8"
                    ).stdout.split()[0]
                if checksum == train_check["checksum"]:
                    return True

                self.middleware.logger.warning("Invalid update file checksum %r, re-downloading", checksum)
                os.unlink(dst)

            for i in itertools.count(1):
                with open(dst, "ab") as f:
                    download_start = time.monotonic()
                    progress = None
                    try:
                        start = os.path.getsize(dst)
                        with requests.get(
                            f"{scale_update_server()}/{train}/{train_check['filename']}",
                            stream=True,
                            timeout=30,
                            headers={"Range": f"bytes={start}-"}
                        ) as r:
                            r.raise_for_status()
                            total = start + int(r.headers["Content-Length"])
                            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                                progress = f.tell()

                                job.set_progress(
                                    progress / total * progress_proportion,
                                    f'Downloading update: {humanfriendly.format_size(total)} at '
                                    f'{humanfriendly.format_size(progress / (time.monotonic() - download_start))}/s'
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

            return True

        return False
