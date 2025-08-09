import os

import yaml

from middlewared.service import job, Service

from .ix_apps.lifecycle import get_current_app_config
from .ix_apps.metadata import get_app_metadata
from .ix_apps.path import get_app_parent_config_path, get_collective_config_path, get_collective_metadata_path
from .ix_apps.utils import QuotedStrDumper


class AppMetadataService(Service):

    class Config:
        namespace = 'app.metadata'
        private = True

    @job(lock='app_metadata_generate', lock_queue_size=1)
    def generate(self, job, blacklisted_apps=None):
        config = {}
        metadata = {}
        blacklisted_apps = blacklisted_apps or []
        with os.scandir(get_app_parent_config_path()) as scan:
            for entry in filter(lambda e: e.name not in blacklisted_apps and e.is_dir(), scan):
                if not (app_metadata := get_app_metadata(entry.name)):
                    # The app is malformed or something is seriously wrong with it
                    continue

                metadata[entry.name] = app_metadata
                config[entry.name] = get_current_app_config(entry.name, app_metadata['version'])

        with open(get_collective_metadata_path(), 'w') as f:
            f.write(yaml.dump(metadata, Dumper=QuotedStrDumper))

        with open(get_collective_config_path(), 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(yaml.dump(config, Dumper=QuotedStrDumper))

        job.set_progress(100, 'Updated metadata configuration for apps')
