import os

from threading import Lock

from middlewared.utils.mount import (move_tree, statmount, umount)
from .utils import SYSDATASET_PATH

VARDB = '/var/db'

SYSDATASET_LOCK = Lock()


def switch_system_dataset_pool(new_pool_name: str) -> bool:
    """
    Atomically swap bind mount out from under /var/db/system with
    the specified pool.

    Returns bool indicating whether mount changed
    """
    from_path = os.path.join(VARDB, f'system_{new_pool_name}')

    with SYSDATASET_LOCK():
        source_sm = statmount(from_path)
        victim_sm = statmount(SYSDATASET_PATH)
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
            SYSDATSET_PATH,
            open_tree_flags=truenas_os.OPEN_TREE_CLONE|truenas_os.OPEN_TREE_CLOEXEC,
            move_mount_flags=move_flags
        )

        if something_mounted:
            umount(SYSDATASET_PATH, recursive=True)

        return True
