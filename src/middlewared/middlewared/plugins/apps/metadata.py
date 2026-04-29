from __future__ import annotations

import os
from typing import TYPE_CHECKING

from truenas_os_pyutils.io import atomic_write

from .ix_apps.lifecycle import get_current_app_config
from .ix_apps.metadata import get_app_metadata
from .ix_apps.path import get_app_parent_config_path, get_collective_config_path, get_collective_metadata_path
from .ix_apps.utils import dump_yaml

if TYPE_CHECKING:
    from middlewared.job import Job


def app_metadata_generate(job: Job, blacklisted_apps: list[str] | None = None) -> None:
    config = {}
    metadata = {}
    blacklisted_apps = blacklisted_apps or []
    with os.scandir(get_app_parent_config_path()) as scan:
        for entry in filter(lambda e: e.name not in blacklisted_apps and e.is_dir(), scan):
            if not (app_metadata := get_app_metadata(entry.name)):
                # The app is malformed or something is seriously wrong with it
                continue

            metadata[entry.name] = app_metadata
            config[entry.name] = get_current_app_config(entry.name, app_metadata["version"])

    with atomic_write(get_collective_metadata_path(), "w") as f:
        f.write(dump_yaml(metadata))

    with atomic_write(get_collective_config_path(), "w", perms=0o600) as f:
        f.write(dump_yaml(config))

    job.set_progress(100, "Updated metadata configuration for apps")
