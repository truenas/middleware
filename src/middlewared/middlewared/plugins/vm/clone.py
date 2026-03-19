from __future__ import annotations

import errno
import itertools
import re
import typing
import uuid

from middlewared.api.current import (
    VMCreate, VMDeviceCreate, VMDeviceEntry,
    ZFSResourceSnapshotCloneQuery, ZFSResourceQuery, ZFSResourceSnapshotDestroyQuery,
    ZFSResourceSnapshotCreateQuery, ZFSResourceSnapshotQuery,
)
from middlewared.plugins.zfs.zvol_utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import CallError, ServiceContext
from middlewared.service_exception import ValidationErrors
from middlewared.utils.libvirt.nic import NICDelegate


if typing.TYPE_CHECKING:
    from middlewared.utils.types import AuditCallback

ZVOL_CLONE_SUFFIX = '_clone'
ZVOL_CLONE_RE = re.compile(rf'^(.*){ZVOL_CLONE_SUFFIX}\d+$')


async def _next_clone_name(context: ServiceContext, name: str) -> str:
    vm_names = [
        i['name']
        for i in await context.middleware.call('datastore.query', 'vm.vm', [
            ('name', '~', rf'{name}{ZVOL_CLONE_SUFFIX}\d+')
        ])
    ]
    clone_index = 0
    while True:
        clone_name = f'{name}{ZVOL_CLONE_SUFFIX}{clone_index}'
        if clone_name not in vm_names:
            break
        clone_index += 1
    return clone_name


async def _clone_zvol(
    context: ServiceContext, name: str, zvol: str, created_snaps: list[str], created_clones: list[str],
) -> str:
    zz = await context.call2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[zvol], properties=None),
    )
    if not zz:
        raise CallError(f'zvol {zvol} does not exist.', errno.ENOENT)

    # Get existing snapshots for this zvol (properties: None for efficiency)
    existing_snaps = await context.call2(context.s.zfs.resource.snapshot.query, ZFSResourceSnapshotQuery(
        paths=[zvol], properties=None,
    ))
    existing_snap_names = {s.name for s in existing_snaps}

    snapshot_name = name
    i = 0
    while True:
        zvol_snapshot = f'{zvol}@{snapshot_name}'
        if zvol_snapshot in existing_snap_names:
            if ZVOL_CLONE_RE.search(snapshot_name):
                snapshot_name = ZVOL_CLONE_RE.sub(rf'\1{ZVOL_CLONE_SUFFIX}{i}', snapshot_name)
            else:
                snapshot_name = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
            i += 1
            continue
        break

    await context.call2(context.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
        dataset=zvol,
        name=snapshot_name,
    ))
    created_snaps.append(zvol_snapshot)

    clone_suffix = name
    i = 0
    while True:
        clone_dst = f'{zvol}_{clone_suffix}'
        if await context.call2(
            context.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[clone_dst], properties=None)
        ):
            if ZVOL_CLONE_RE.search(clone_suffix):
                clone_suffix = ZVOL_CLONE_RE.sub(rf'\1{ZVOL_CLONE_SUFFIX}{i}', clone_suffix)
            else:
                clone_suffix = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
            i += 1
            continue
        break

    await context.call2(context.s.zfs.resource.snapshot.clone, ZFSResourceSnapshotCloneQuery(
        snapshot=zvol_snapshot,
        dataset=clone_dst,
    ))

    created_clones.append(clone_dst)

    return clone_dst


def validate_clone(vm_devices: list[VMDeviceEntry]) -> None:
    verrors = ValidationErrors()
    for index, device in enumerate(vm_devices):
        if device.attributes.dtype == 'DISPLAY' and not device.attributes.password:
            verrors.add(
                f'vm.devices.{index}.attributes.password',
                'Password must be configured for display device in order to clone the VM.'
            )
    verrors.check()


async def clone_vm(context: ServiceContext, id_: int, name: str | None, *, audit_callback: AuditCallback) -> bool:
    vm = await context.call2(context.s.vm.get_instance, id_)
    audit_callback(f'{vm.name} to {name or "auto"}')
    validate_clone(vm.devices)

    origin_name = vm.name
    clone_name = name if name is not None else await _next_clone_name(context, vm.name)

    # Build VMCreate from the existing VM entry, overriding name and uuid
    vm_dict = vm.model_dump(by_alias=True)
    for key in ('id', 'status', 'display_available', 'devices'):
        vm_dict.pop(key, None)
    vm_dict['name'] = clone_name
    vm_dict['uuid'] = str(uuid.uuid4())  # We want to use a newer uuid here as it is supposed to be unique per VM
    create_data = VMCreate.model_validate(vm_dict)

    created_snaps: list[str] = []
    created_clones: list[str] = []
    try:
        new_vm = await context.call2(context.s.vm.create, create_data)

        for device in vm.devices:
            device_dict = device.model_dump(by_alias=True, context={'expose_secrets': True})
            device_dict.pop('id', None)
            device_dict['vm'] = new_vm.id
            dtype = device.attributes.dtype

            if dtype == 'NIC':
                device_dict['attributes']['mac'] = NICDelegate.random_mac()
            if dtype == 'DISPLAY':
                if 'port' in device_dict['attributes']:
                    port_dev = await context.call2(context.s.vm.port_wizard)
                    device_dict['attributes']['port'] = port_dev.port
                    device_dict['attributes']['web_port'] = port_dev.web
            if dtype == 'DISK':
                zvol = zvol_path_to_name(device_dict['attributes']['path'])
                device_dict['attributes']['path'] = zvol_name_to_path(
                    await _clone_zvol(context, clone_name, zvol, created_snaps, created_clones)
                )
            if dtype == 'RAW':
                context.logger.warning('RAW disks must be copied manually. Skipping...')
                continue

            await context.call2(context.s.vm.device.create, VMDeviceCreate.model_validate(device_dict))
    except Exception as e:
        for clone, snap in itertools.zip_longest(reversed(created_clones), reversed(created_snaps)):
            if clone is not None:
                try:
                    context.call_sync2(context.s.zfs.resource.destroy_impl, clone)
                except Exception:
                    context.logger.exception('Failed to destroy cloned zvol %r', clone)
                    continue
                else:
                    if snap is not None:
                        try:
                            await context.call2(
                                context.s.zfs.resource.snapshot.destroy_impl,
                                ZFSResourceSnapshotDestroyQuery(path=snap),
                            )
                        except Exception:
                            context.logger.exception('Failed to destroy snapshot %r for zvol %r', snap, clone)
        raise e

    context.logger.info('VM cloned from %r to %r', origin_name, clone_name)
    return True
