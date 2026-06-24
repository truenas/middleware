from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import CloudBackupRestoreOptions
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.cloud_backup.restic import get_restic_config, run_restic
from middlewared.plugins.cloud_backup.utils import resolve_credentials
from middlewared.service import ServiceContext, ValidationErrors

if TYPE_CHECKING:
    from middlewared.job import Job


def do_restore(
    context: ServiceContext,
    job: Job,
    id_: int,
    snapshot_id: str,
    subfolder: str,
    destination_path: str,
    options: CloudBackupRestoreOptions,
) -> None:
    context.middleware.call_sync("network.general.will_perform_activity", "cloud_backup")

    verrors = ValidationErrors()
    context.middleware.run_coroutine(
        check_path_resides_within_volume(verrors, context.middleware, "destination_path", destination_path)
    )
    verrors.check()

    entry = context.call_sync2(context.s.cloud_backup.get_instance, id_)

    credentials = resolve_credentials(context, entry.credentials)
    restic_config = get_restic_config(entry, credentials)

    cmd = ["restore", f"{snapshot_id}:{subfolder}", "--target", destination_path]
    cmd += sum([["--exclude", exclude] for exclude in options.exclude], [])
    cmd += sum([["--include", include] for include in options.include], [])
    if limit := (options.rate_limit or entry.rate_limit):
        cmd.append(f"--limit-download={limit}")

    run_restic(
        job,
        restic_config.cmd + cmd,
        restic_config.env,
        track_progress=True,
    )
