import tempfile

import yaml

from middlewared.plugins.apps.utils import run


def migrate_chart_release_config(release_data: dict) -> dict | str:
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(yaml.dump(release_data))
        f.flush()

        cp = run([release_data['migrate_file_path'], f.name])
        if cp.returncode:
            return f'Failed to migrate config: {cp.stderr}'

        if not cp.stdout:
            error = 'No output from migration script'
        else:
            try:
                return yaml.safe_load(cp.stdout)
            except yaml.YAMLError:
                error = 'Failed to parse migrated config'

        return f'Failed to migrate config: {error}'
