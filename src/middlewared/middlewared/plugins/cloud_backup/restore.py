from middlewared.plugins.cloud_backup.restic import get_restic_config, run_restic
from middlewared.schema import accepts, Dict, Int, List, Str
from middlewared.service import job, Service
from middlewared.validators import NotMatch


class CloudBackupService(Service):

    class Config:
        cli_namespace = "task.cloud_backup"
        namespace = "cloud_backup"

    @accepts(
        Int("id"),
        Str("snapshot_id", validators=[NotMatch(r"^-")]),
        Str("subfolder"),
        Str("destination_path", validators=[NotMatch(r"^-")]),
        Dict(
            "options",
            List("exclude", items=[Str("item")]),
            List("include", items=[Str("item")]),
        ),
    )
    @job(logs=True)
    async def restore(self, job, id_, snapshot_id, subfolder, destination_path, options):
        """
        Restore files to the directory `destination_path` from the `snapshot_id` subfolder `subfolder`
        created by the cloud backup job `id`.
        """
        await self.middleware.call("network.general.will_perform_activity", "cloud_backup")

        cloud_backup = await self.middleware.call("cloud_backup.get_instance", id_)

        restic_config = get_restic_config(cloud_backup)

        cmd = ["restore", f"{snapshot_id}:{subfolder}", "--target", destination_path]
        cmd += sum([["--exclude", exclude] for exclude in options["exclude"]], [])
        cmd += sum([["--include", include] for include in options["include"]], [])

        await run_restic(
            job,
            restic_config.cmd + cmd,
            restic_config.env,
        )
