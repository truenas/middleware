import json
import logging
import os

from middlewared.service import CallError, private, Service

from .utils import SCALE_MANIFEST_FILE, can_update
from .utils_linux import mount_update

logger = logging.getLogger(__name__)


class UpdateService(Service):
    @private
    def install_impl(self, job, location):
        self._install(
            os.path.join(location, "update.sqsh"),
            lambda progress, description: job.set_progress((0.5 + 0.5 * progress) * 100, description),
        )

    @private
    def install_manual_impl(self, job, path, dest_extracted):
        self._install(
            path,
            lambda progress, description: job.set_progress((0.5 + 0.5 * progress) * 100, description),
        )

    def _install(self, path, progress_callback):
        with open(SCALE_MANIFEST_FILE) as f:
            old_manifest = json.load(f)

        progress_callback(0, "Reading update file")
        with mount_update(path) as mounted:
            with open(os.path.join(mounted, "manifest.json")) as f:
                manifest = json.load(f)

            old_version = old_manifest["version"]
            new_version = manifest["version"]
            if not can_update(old_version, new_version):
                raise CallError(f'Unable to downgrade from {old_version} to {new_version}')

            self.middleware.call_sync("update.install_scale", mounted, progress_callback)
