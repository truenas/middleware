import json
import logging
import os

from middlewared.plugins.config import UPLOADED_DB_PATH
from middlewared.service import CallError, private, Service
from middlewared.utils import sw_info

from .utils import can_update
from .utils_linux import mount_update

logger = logging.getLogger(__name__)


class UpdateService(Service):
    @private
    def install(self, job, path, options, max_progress=100):
        if os.path.exists(UPLOADED_DB_PATH):
            raise CallError(
                "An unapplied uploaded configuration exists. Please, reboot the system to apply this configuration "
                "before running upgrade."
            )

        state = self.middleware.call_sync("boot.get_state")
        if (
            state["scan"] and
            state["scan"]["function"] == "RESILVER" and
            state["scan"]["state"] == "SCANNING"
        ):
            raise CallError(
                "One or more boot pool devices are currently being resilvered. The upgrade cannot continue "
                "until the resilvering operation is finished."
            )

        def progress_callback(progress, description):
            job.set_progress((0.5 + 0.5 * progress) * max_progress, description)

        progress_callback(0, "Reading update file")
        with mount_update(path) as mounted:
            with open(os.path.join(mounted, "manifest.json")) as f:
                manifest = json.load(f)

            old_version = sw_info()['version']
            new_version = manifest["version"]
            if old_version == new_version:
                raise CallError(f'You already are using {new_version}')
            if not can_update(old_version, new_version):
                raise CallError(f'Unable to downgrade from {old_version} to {new_version}')

            self.middleware.call_sync("update.install_scale", mounted, progress_callback, options)
