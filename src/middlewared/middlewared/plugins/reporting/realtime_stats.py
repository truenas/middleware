from __future__ import annotations

import time
import typing

from middlewared.service import ServiceContext
from middlewared.utils.disks import get_disk_names
from middlewared.utils.disks_.disk_class import iterate_disks

from .realtime_reporting import (
    get_arc_stats,
    get_cpu_stats,
    get_disk_stats,
    get_interface_stats,
    get_memory_info,
    get_pool_stats,
)


def get_disks_with_identifiers() -> dict[str, str]:
    return {i.name: i.identifier for i in iterate_disks()}


def stats(context: ServiceContext, disk_mapping: dict[str, str] | None = None) -> dict[str, typing.Any]:
    disk_mapping = disk_mapping or get_disks_with_identifiers()
    # this gathers the most recent metric recorded via netdata (for all charts)
    retries = 2
    netdata_metrics = None
    while retries > 0:
        try:
            netdata_metrics = context.middleware.call_sync("netdata.get_all_metrics")
        except Exception:
            retries -= 1
            if retries <= 0:
                raise

            time.sleep(0.5)
        else:
            break

    data: dict[str, typing.Any] = dict()
    if netdata_metrics:
        disks = get_disk_names()
        if len(disks) != len(disk_mapping):
            disk_mapping = get_disks_with_identifiers()

        data.update(
            {
                "zfs": get_arc_stats(netdata_metrics),  # ZFS ARC Size
                "memory": get_memory_info(netdata_metrics),
                "cpu": get_cpu_stats(netdata_metrics),
                "disks": get_disk_stats(netdata_metrics, disks, disk_mapping),
                "interfaces": get_interface_stats(
                    netdata_metrics,
                    [
                        iface["name"]
                        for iface in context.middleware.call_sync(
                            "interface.query", [], {"extra": {"retrieve_names_only": True}}
                        )
                    ],
                ),
                "pools": get_pool_stats(netdata_metrics),
            }
        )

    return data
