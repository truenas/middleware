import os

from threading import Lock

import truenas_os
from middlewared.utils import MIDDLEWARE_RUN_DIR
from middlewared.utils.mount import (move_tree, statmount, umount)
from .utils import POOL_SYSDATASET_PREFIX, SYSDATASET_PATH, TMP_SYSDATASET_PREFIX

SYSDATASET_LOCK = Lock()


def switch_system_dataset_pool(new_pool_name: str) -> bool:
    """
    Atomically swap bind mount out from under /var/db/system with
    the specified pool.

    Returns bool indicating whether mount changed
    """
    from_path = f'{POOL_SYSDATASET_PREFIX}{new_pool_name}'

    with SYSDATASET_LOCK:
        source_sm = statmount(path=from_path, as_dict=False)
        victim_sm = statmount(path=SYSDATASET_PATH, as_dict=False)
        victim_pool = victim_sm.sb_source.split('/')[0]

        # We may in theory have boot pool that just has directory and no
        # system dataset mounted on it.
        something_mounted = victim_sm.sb_source.endswith('.system')
        move_flags = truenas_os.MOVE_MOUNT_BENEATH if something_mounted else 0

        if new_pool_name == victim_pool and something_mounted:
            # We already have correct filesystem mounted. Shortcircuit
            return False

        move_tree(
            from_path,
            SYSDATASET_PATH,
            open_tree_flags=truenas_os.OPEN_TREE_CLONE|truenas_os.OPEN_TREE_CLOEXEC,
            move_mount_flags=move_flags
        )

        if something_mounted:
            # Now we want to move the top directory away so that we can try an unmount
            # This allows processes to immediately start consuming the new paths
            # while the system dataset possibly lazily umounts.
            victim_tmp_mp = f'{TMP_SYSDATASET_PREFIX}{victim_pool}'
            os.makedirs(victim_tmp_mp, exist_ok=True)

            move_tree(SYSDATASET_PATH, victim_tmp_mp)
            umount(victim_tmp_mp, detach=True, recursive=True)

        return True
