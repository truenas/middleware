import os

SYSDATASET_PATH = '/var/db/system'


def dataset_mountpoint(ds: dict) -> str:
    """Absolute path where system-dataset spec entry `ds` is mounted.

    Honors an explicit ``mountpoint`` override -- a UUID-named per-controller
    dataset (e.g. ``.system/netdata-{uuid}``) pins to a stable well-known path
    (``/var/db/system/netdata``) that both HA controllers and the dataset's
    consumers agree on. Otherwise the path is the dataset basename under
    SYSDATASET_PATH. Single source of truth for mount-path resolution so
    mount_hierarchy and _finalize_datasets can't drift.
    """
    return ds.get('mountpoint') or os.path.join(SYSDATASET_PATH, os.path.basename(ds['name']))
