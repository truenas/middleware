# -*- coding=utf-8 -*-
from freenasOS import Update

from middlewared.service import private, Service

from .utils_freebsd import UpdateHandler


class UpdateService(Service):
    @private
    def download_impl(self, job, train, location, progress_proportion):
        job.set_progress(0, 'Retrieving update manifest')

        handler = UpdateHandler(self, job, progress_proportion)

        Update.DownloadUpdate(
            train,
            location,
            check_handler=handler.check_handler,
            get_handler=handler.get_handler,
        )
        update = Update.CheckForUpdates(train=train, cache_dir=location)

        return bool(update)
