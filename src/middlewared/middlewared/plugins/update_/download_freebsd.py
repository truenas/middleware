# -*- coding=utf-8 -*-
import contextlib
import json
import os

from freenasOS import Update

from middlewared.service import private, Service

from .utils_freebsd import UpdateHandler


class UpdateService(Service):
    @private
    def download_impl(self, job, train, location, progress_proportion):
        scale_flag = os.path.join(location, 'scale')

        if 'SCALE' in train:
            scale_manifest = self.middleware.call_sync('update.get_scale_manifest', train)
            result = self.middleware.call_sync('update.download_impl_scale', job, train, location, progress_proportion)

            if result:
                with open(scale_flag, 'w') as f:
                    json.dump(scale_manifest, f)

            return result

        job.set_progress(0, 'Retrieving update manifest')

        handler = UpdateHandler(self, job, progress_proportion)

        Update.DownloadUpdate(
            train,
            location,
            check_handler=handler.check_handler,
            get_handler=handler.get_handler,
        )
        update = Update.CheckForUpdates(train=train, cache_dir=location)

        result = bool(update)

        if result:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(scale_flag)

        return result
