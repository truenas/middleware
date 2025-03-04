import contextlib

import libzfs


def get_pool_dataset_stats() -> dict[str, dict]:
    pool_stats = {}
    kwargs = {
        'props': ['used', 'available'],
        'user_props': True,
        'snapshots': None,
        'retrieve_children': False,
        'snapshots_recursive': None,
        'snapshot_props': [],
    }
    with contextlib.suppress(libzfs.ZFSException):
        # We want to suppress it because if a plugin errors out once, it won't run again
        # unless netdata is restarted
        with libzfs.ZFS() as zfs:
            dataset_info = list(zfs.datasets_serialized(**kwargs))
            for info in dataset_info:
                pool_stats[info['id']] = {
                    'available': info['properties']['available']['parsed'],
                    'used': info['properties']['used']['parsed'],
                }

    return pool_stats
