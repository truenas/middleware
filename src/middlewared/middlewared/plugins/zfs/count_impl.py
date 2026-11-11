import dataclasses
from typing import Any

from truenas_pylibzfs import ZFSProperty, ZFSType

__all__ = ("ResourceCounts", "count_resources_impl")


@dataclasses.dataclass(slots=True)
class ResourceCounts:
    datasets: int = 0
    zvols: int = 0
    zvols_used: int = 0


def __count_resource_callback(hdl: Any, counts: ResourceCounts) -> bool:
    if hdl.type == ZFSType.ZFS_TYPE_VOLUME:
        counts.zvols += 1
        counts.zvols_used += hdl.get_properties(properties={ZFSProperty.USED}).used.value
    else:
        counts.datasets += 1
        # Simple handles make the kernel skip building each dataset's property list
        hdl.iter_filesystems(callback=__count_resource_callback, state=counts, fast=True)
    return True


def count_resources_impl(tls: Any) -> ResourceCounts:
    counts = ResourceCounts()
    tls.lzh.iter_root_filesystems(callback=__count_resource_callback, state=counts)
    return counts
