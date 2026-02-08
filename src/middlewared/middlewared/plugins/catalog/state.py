from __future__ import annotations

import os

from middlewared.plugins.docker.state_utils import catalog_ds_path, CATALOG_DATASET_NAME
from middlewared.service import ServiceContext


async def dataset_mounted(context: ServiceContext) -> bool:
    if docker_ds := (await context.middleware.call('docker.config'))['dataset']:
        expected_source = os.path.join(docker_ds, CATALOG_DATASET_NAME)
        catalog_path = catalog_ds_path()
        try:
            sfs = await context.middleware.call('filesystem.statfs', catalog_path)
            return sfs['source'] == expected_source and sfs['fstype'] == 'zfs'
        except Exception:
            return False

    return False
