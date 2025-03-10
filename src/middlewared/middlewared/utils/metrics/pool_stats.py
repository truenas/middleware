import json
import subprocess

from middlewared.utils.zfs import guid_fast_impl


def get_pool_dataset_stats() -> dict[str, dict]:
    pool_stats = {}

    zfs_data = json.loads(subprocess.run(
        ['zfs', 'list', '-o', 'used,avail', '-j', '--json-int', '-d', '0'],
        capture_output=True, text=True, check=True,
    ).stdout.strip())
    for dataset_info in zfs_data['datasets'].values():
        pool_stats[guid_fast_impl(dataset_info['name'])] = {
            key: value['value'] for key, value in dataset_info['properties'].items()
        }

    return pool_stats
