# -*- coding=utf-8 -*-
import os
import subprocess
import time

import humanfriendly
import requests

from middlewared.service import private, Service

from .utils import scale_update_server


class UpdateService(Service):
    @private
    def download_impl(self, job, train, location, progress_proportion):
        job.set_progress(0, "Retrieving update manifest")

        train_check = self.middleware.call_sync("update.check_train", train)
        if train_check["status"] == "AVAILABLE":
            dst = os.path.join(location, "update.sqsh")
            if os.path.exists(dst):
                job.set_progress(0, "Verifying existing update")
                checksum = subprocess.run(
                    ["sha256sum", dst], stdout=subprocess.PIPE, encoding="utf-8"
                ).stdout.split()[0]
                if checksum == train_check["checksum"]:
                    return True

                self.middleware.logger.warning("Invalid update file checksum %r, re-downloading", checksum)
                os.unlink(dst)

            with open(dst, "wb") as f:
                download_start = time.monotonic()
                with requests.get(
                    f"{scale_update_server()}/{train}/{train_check['filename']}",
                    stream=True,
                    timeout=30,
                ) as r:
                    r.raise_for_status()
                    for i in r.iter_content(chunk_size=8 * 1024 * 1024):
                        progress = f.tell()
                        total = int(r.headers["Content-Length"])

                        job.set_progress(
                            progress / total * progress_proportion,
                            f'Downloading update: {humanfriendly.format_size(total)} at '
                            f'{humanfriendly.format_size(progress / (time.monotonic() - download_start))}/s'
                        )

                        f.write(i)

            return True

        return False
