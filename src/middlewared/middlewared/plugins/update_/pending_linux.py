import json
import os

from middlewared.service import private, Service
from .utils import SCALE_MANIFEST_FILE, DOWNLOAD_UPDATE_FILE
from .utils_linux import mount_update


class UpdateService(Service):
    @private
    def get_pending_in_path(self, path):
        if not os.path.exists(os.path.join(path, DOWNLOAD_UPDATE_FILE)):
            return []

        with open(SCALE_MANIFEST_FILE) as f:
            old_manifest = json.load(f)

        try:
            with mount_update(os.path.join(path, DOWNLOAD_UPDATE_FILE)) as mounted:
                with open(os.path.join(mounted, "manifest.json")) as f:
                    new_manifest = json.load(f)
        except Exception:
            self.middleware.logger.error("Failed reading update", exc_info=True)
            return []

        return [
            {
                "operation": "upgrade",
                "old": {
                    "name": "TrueNAS",
                    "version": old_manifest["version"],
                },
                "new": {
                    "name": "TrueNAS",
                    "version": new_manifest["version"],
                }
            }
        ]
