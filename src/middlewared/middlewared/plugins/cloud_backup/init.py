import subprocess

from middlewared.plugins.cloud_backup.restic import get_restic_config
from middlewared.service import CallError, Service, private


class IncorrectPassword(CallError):
    pass


class CloudBackupService(Service):

    class Config:
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @private
    def ensure_initialized(self, cloud_backup):
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        if isinstance(cloud_backup["credentials"], int):
            cloud_backup = {
                **cloud_backup,
                "credentials": self.middleware.call_sync("cloudsync.credentials.get_instance",
                                                         cloud_backup["credentials"]),
            }

        if self.is_initialized(cloud_backup):
            return

        self.init(cloud_backup)

    @private
    def is_initialized(self, cloud_backup):
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        restic_config = get_restic_config(cloud_backup)

        try:
            subprocess.run(
                restic_config.cmd + ["cat", "config"],
                env=restic_config.env,
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            text = e.stderr.strip()

            if "Is there a repository at the following location?" in text:
                return False

            if "wrong password or no key found" in text:
                raise IncorrectPassword(text)

            raise CallError(text)

    @private
    def init(self, cloud_backup):
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        restic_config = get_restic_config(cloud_backup)

        try:
            subprocess.run(
                restic_config.cmd + ["init"],
                env=restic_config.env,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise CallError(e.stderr)
