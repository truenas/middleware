from middlewared.api import api_method
from middlewared.api.current import CloudBackupRestoreArgs, CloudBackupRestoreResult
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.cloud_backup.restic import get_restic_config, run_restic
from middlewared.service import job, Service, ValidationErrors


class CloudBackupService(Service):

    class Config:
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @api_method(CloudBackupRestoreArgs, CloudBackupRestoreResult, roles=["FILESYSTEM_DATA_WRITE"])
    @job(logs=True)
    def restore(self, job, id_, snapshot_id, subfolder, destination_path, options):
        """
        Restore files to the directory `destination_path` from the `snapshot_id` subfolder `subfolder`
        created by the cloud backup job `id`.
        """
        self.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

        verrors = ValidationErrors()

        self.middleware.run_coroutine(
            check_path_resides_within_volume(verrors, self.middleware, "destination_path", destination_path)
        )

        verrors.check()

        cloud_backup = self.middleware.call_sync("cloud_backup.get_instance", id_)

        restic_config = get_restic_config(cloud_backup)

        cmd = ["restore", f"{snapshot_id}:{subfolder}", "--target", destination_path]
        cmd += sum([["--exclude", exclude] for exclude in options["exclude"]], [])
        cmd += sum([["--include", include] for include in options["include"]], [])
        if limit := (options["rate_limit"] or cloud_backup["rate_limit"]):
            cmd.append(f"--limit-download={limit}")

        run_restic(
            job,
            restic_config.cmd + cmd,
            restic_config.env,
            track_progress=True,
        )
