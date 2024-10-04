from logging import getLogger
from os import scandir

from .disk_class import Disk
from .pattern import REPATTERNS

logger = getLogger(__name__)


def enumerate_disks_from_dev() -> list | list[Disk]:
    """Iterating over /dev is the safest route for getting a list of
    disks. One, non-obvious, reason for using /dev/ is that our HA
    systems will mount disks between the nodes across the heartbeat
    connection. These are used for iSCSI ALUA configurations. However,
    they are hidden and so don't surface in the /dev/ directory. If we
    were to use any other directory (/sys/block, /proc, etc) we run
    risk of enumerating those devices and breaking fenced."""
    disks = list()
    try:
        with scandir("/dev") as sdir:
            for disk in filter(lambda x: REPATTERNS.is_valid(x.name), sdir):
                disks.append(disk.name)
    except Exception:
        logger.error("Unhandled exception enumerating disks", exc_info=True)

    return disks
