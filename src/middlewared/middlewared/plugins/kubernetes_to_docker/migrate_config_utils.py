import tempfile

import yaml

from middlewared.plugins.apps.utils import run


def migrate_chart_release_config(release_data: dict) -> dict | str:
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(yaml.dump(release_data))
        f.flush()

        # TODO: Probably no need to do /usr/bin/python3
        # Catalog at this point would be in /var/run and we can't execute an executable there
        cp = run(['/usr/bin/python3', release_data['migrate_file_path'], f.name])
        if cp.returncode:
            return f'Failed to migrate config: {cp.stderr}'

        if not cp.stdout:
            error = 'No output from migration script'
        else:
            try:
                new_config = yaml.safe_load(cp.stdout)
            except yaml.YAMLError:
                error = 'Failed to parse migrated config'
            else:
                if new_config:
                    return new_config
                else:
                    error = 'No migrated config found'

        return f'Failed to migrate config: {error}'
