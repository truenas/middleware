from __future__ import annotations

import collections
import os
import typing

from middlewared.api.current import VMCDROMDevice, VMDeviceEntry, VMDiskDevice, VMRAWDevice
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.service import ServiceContext
from middlewared.utils.libvirt.utils import ACTIVE_STATES


async def determine_recursive_search(
    recursive: bool, device: VMDeviceEntry, child_datasets: dict[str, typing.Any]
) -> bool:
    # TODO: Add unit tests for this please
    if recursive:
        return True
    elif isinstance(device.attributes, VMDiskDevice):
        return False

    # What we want to do here is make sure that any raw files or cdrom files are not living in the child
    # dataset and not affected by the parent snapshot as they live on a different filesystem
    if not isinstance(device.attributes, (VMCDROMDevice, VMRAWDevice)):
        raise ValueError('Device must be VMCDROMDevice or VMRAWDevice')

    path = device.attributes.path.removeprefix('/mnt/')
    for split_count in range(path.count('/')):
        potential_ds = path.rsplit('/', split_count)[0]
        if potential_ds in child_datasets:
            return False
    else:
        return True


async def get_vms_to_ignore_for_querying_attachments(
    context: ServiceContext, enabled: bool, extra_filters: list[typing.Any] | None = None
) -> list[int]:
    extra_filters = extra_filters or []
    return [
        vm.id for vm in await context.call2(
            context.s.vm.query, [('status.state', 'nin' if enabled else 'in', ACTIVE_STATES)] + extra_filters
        )
    ]


async def query_snapshot_begin(
    context: ServiceContext, dataset: str, recursive: bool
) -> dict[int, list[dict[str, typing.Any]]]:
    vms = collections.defaultdict(list)
    datasets = {
        d['id']: d for d in await context.middleware.call(
            'pool.dataset.query', [['id', '^', f'{dataset}/']], {'extra': {'properties': []}}
        )
    }
    to_ignore_vms = await get_vms_to_ignore_for_querying_attachments(
        context, True, [['suspend_on_snapshot', '=', False]]
    )
    for device in await context.call2(
        context.s.vm.device.query, [
            ['attributes.dtype', 'in', ('DISK', 'RAW', 'CDROM')],
            ['vm', 'nin', to_ignore_vms],
        ]
    ):
        if not isinstance(device.attributes, (VMDiskDevice, VMRAWDevice, VMCDROMDevice)):
            continue
        path = device.attributes.path
        if not path:
            continue
        elif path.startswith('/dev/zvol'):
            path = os.path.join('/mnt', zvol_path_to_name(path))

        dataset_path = os.path.join('/mnt', dataset)
        if await determine_recursive_search(recursive, device, datasets):
            if await context.middleware.call('filesystem.is_child', path, dataset_path):
                vms[device.vm].append(device.model_dump(by_alias=True))
        elif dataset_path == path:
            vms[device.vm].append(device.model_dump(by_alias=True))

    return vms


async def periodic_snapshot_task_begin(context: ServiceContext, task_id: int) -> dict[int, list[dict[str, typing.Any]]]:
    task = await context.call2(context.s.pool.snapshottask.get_instance, task_id)
    return await query_snapshot_begin(context, task.dataset, task.recursive)
