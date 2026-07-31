from __future__ import annotations

import ipaddress
import os
import typing

import yaml

from middlewared.api.current import ContainerEntry, ZFSResourceQuery
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.service import CallError, ServiceContext
import middlewared.sqlalchemy as sa

from .crud import ContainerCreateWithDataset
from .dataset import ensure_datasets
from .info import license_active
from .utils import container_dataset

if typing.TYPE_CHECKING:
    from middlewared.job import Job


class VirtGlobalModel(sa.Model):
    """Legacy virt_global table model for migration purposes."""
    __tablename__ = 'virt_global'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(120), nullable=True)
    storage_pools = sa.Column(sa.Text(), nullable=True)
    bridge = sa.Column(sa.String(120), nullable=True)
    v4_network = sa.Column(sa.String(120), nullable=True)
    v6_network = sa.Column(sa.String(120), nullable=True)


async def maybe_migrate_legacy(context: ServiceContext) -> None:
    """
    Check for legacy incus containers and auto-migrate if found.

    Called on system ready. If virt_global.pool is set, legacy containers
    exist and need migration. On success, sets preferred_pool and clears
    virt_global.pool so migration does not re-trigger on next boot.
    """
    legacy_config = await context.middleware.call('datastore.query', 'virt.global')
    if not legacy_config or legacy_config[0]['pool'] is None:
        return

    legacy_config = legacy_config[0]
    if await context.middleware.call('system.is_ha_capable'):
        # Legacy containers were never migrated on a controller that can be paired, so
        # there is no established path here and no reason to take the risk of inventing
        # one during a failover event. The pool is cleared so this is not reconsidered
        # on every boot; nothing on disk is touched, the legacy datasets stay as they
        # are under `.ix-virt` if some user somehow was still using it.
        context.logger.warning(
            'Legacy virt pool was found set but this system is HA capable; migration skipped.'
        )
        await context.middleware.call(
            'datastore.update', 'virt.global', legacy_config['id'], {'pool': None},
        )
        return

    if not await license_active(context):
        # Returning before virt_global.pool is cleared leaves the legacy
        # configuration intact, so the migration runs on a later boot once
        # the license is in place. Nothing on disk is touched meanwhile.
        context.logger.warning(
            'Legacy incus containers found but this system is not licensed to use containers; '
            'migration deferred.'
        )
        return

    context.logger.info('Legacy incus container configuration found, starting migration')
    try:
        migration_job = await context.call2(context.s.container.migrate)
        await migration_job.wait(raise_error=True)
    except Exception:
        context.logger.error('Legacy container migration failed', exc_info=True)
        return

    container_config = await context.call2(context.s.lxc.config)
    updates = {}
    if container_config.preferred_pool is None:
        updates['preferred_pool'] = legacy_config['pool']

    for col in ('bridge', 'v4_network', 'v6_network'):
        if not legacy_config.get(col):
            continue

        value = legacy_config[col]
        if col in ('v4_network', 'v6_network'):
            try:
                value = str(ipaddress.ip_network(value, strict=False))
            except (ValueError, TypeError):
                continue

        updates[col] = value

    if updates:
        await context.middleware.call(
            'datastore.update', 'container.config', container_config.id, updates,
        )

    await context.middleware.call(
        'datastore.update', 'virt.global', legacy_config['id'],
        {'pool': None},
    )
    context.logger.info('Legacy container migration completed')


async def migrate(context: ServiceContext, job: Job) -> None:
    legacy_configuration = await context.middleware.call('datastore.query', 'virt.global')
    if not legacy_configuration or legacy_configuration[0]['pool'] is None:
        raise CallError('Legacy containers configuration pool is not set.')

    # Every migrated container has to pass container.validate, which fails
    # without a license. Bailing out here leaves the legacy datasets untouched
    # instead of moving them somewhere no container row can point at.
    if not await license_active(context):
        raise CallError('System is not licensed to use containers.')

    pool = legacy_configuration[0]['pool']

    storage_pools = {pool} | set(filter(bool, (legacy_configuration[0]['storage_pools'] or '').split()))
    existing_containers = [container.name for container in await context.call2(context.s.container.query)]
    for storage_pool in storage_pools:
        # One unusable pool must not stop the pools that come after it.
        try:
            await context.to_thread(migrate_specific_pool, context, job, storage_pool, existing_containers)
        except Exception as e:
            context.logger.error('Unable to migrate containers on pool %r', storage_pool, exc_info=True)
            await job.logs_fd_write(
                f'Unable to migrate containers on pool {storage_pool!r}: {e!r}.\n'.encode()
            )


async def migrate_devices(
    context: ServiceContext, job: Job, manifest: dict[str, typing.Any], container_instance: ContainerEntry
) -> None:
    devices = manifest['devices']
    container_name = container_instance.name
    nic_choices = await context.call2(context.s.container.device.nic_attach_choices)
    all_nic_choices = set(nic_choices.BRIDGE) | set(nic_choices.MACVLAN)
    gpu_choices = await context.call2(context.s.container.device.gpu_choices)
    for device_name, device_data in devices.items():
        dtype = None
        try:
            device_payload = None
            dtype = device_data.get('type')
            if dtype == 'disk':
                src = device_data.get('source', "")
                if src.startswith('/mnt') is False:
                    await job.logs_fd_write((
                        f'Skipping migrating {device_name!r} disk device for {container_name!r} because '
                        f'source does not start with /mnt/ (is {src!r} instead)\n'
                    ).encode())
                    continue

                device_payload = {
                    'dtype': 'FILESYSTEM',
                    'source': src,
                    'target': device_data['path'],
                }
            elif dtype == 'nic':
                if device_data.get('parent') not in all_nic_choices:
                    await job.logs_fd_write((
                        f'Skipping migrating {device_name!r} NIC device for {container_name!r} because '
                        f'{device_data.get('parent')!r} is not a valid NIC\n'
                    ).encode())
                    continue

                device_payload = {
                    'dtype': 'NIC',
                    'nic_attach': device_data['parent'],
                    'type': 'VIRTIO',
                    'trust_guest_rx_filters': False,
                    'mac': manifest['config'].get(f'volatile.{device_name}.hwaddr')
                }
            elif dtype == 'usb':
                if (bus_num := device_data.get('busnum')) and (devnum := device_data.get('devnum')):
                    device_payload = {
                        'dtype': 'USB',
                        'device': f'usb_{bus_num}_{devnum}',
                        'usb': None,
                    }
                elif (vendor_id := device_data.get('vendorid')) and (product_id := device_data.get('productid')):
                    device_payload = {
                        'dtype': 'USB',
                        'usb': {'vendor_id': f'0x{vendor_id}', 'product_id': f'0x{product_id}'},
                        'device': None
                    }
                else:
                    await job.logs_fd_write((
                        f'Skipping migration of USB device {device_name!r} for container {container_name!r} '
                        'because the USB data is invalid or incomplete\n'
                    ).encode())
                    continue

            elif dtype == 'gpu':
                pci_address = device_data.get('pci')
                if pci_address not in gpu_choices:
                    await job.logs_fd_write((
                        f'Skipping migrating {device_name!r} GPU device for {container_name!r} because '
                        f'{pci_address!r} is not a valid PCI address for a GPU device\n'
                    ).encode())
                    continue

                device_payload = {
                    'dtype': 'GPU',
                    'gpu_type': gpu_choices[pci_address],
                    'pci_address': pci_address,
                }
            else:
                await job.logs_fd_write((
                    f'Skipping migrating {device_name!r} device for {container_name!r} because '
                    f'unhandled device type {dtype!r} found\n'
                ).encode())
        except Exception as e:
            await job.logs_fd_write(
                f'Unable to migrate {device_name!r} {dtype} device for {container_name!r}: {e!r}.\n'.encode()
            )
            continue
        else:
            if device_payload:
                try:
                    await context.middleware.call(
                        'datastore.insert', 'container.device', {
                            'attributes': device_payload,
                            'container_id': container_instance.id,
                        }
                    )
                except Exception as e:
                    # Should not happen but better safe than sorry
                    await job.logs_fd_write(
                        f'Unable to create container device for {device_name!r} {dtype} incus '
                        f'device: {e!r}.\n'.encode()
                    )


def migrate_specific_pool(context: ServiceContext, job: Job, pool: str, existing_containers: list[str]) -> None:
    assert job.logs_fd is not None
    processed_parents_mountpoints = False
    datasets = context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(
            paths=[f'{pool}/.ix-virt/containers'],
            get_children=True,
            properties=None
        )
    )
    if datasets:
        context.run_coroutine(ensure_datasets(context, pool))

    for dataset in datasets:
        if dataset['type'] != 'FILESYSTEM':
            continue

        split = dataset['name'].split('/')
        if len(split) != 4:
            job.logs_fd.write(
                f'Skipping dataset {dataset['name']} during migration (not a container dataset)'.encode(),
            )
            continue

        name = split[-1]
        if name in existing_containers:
            job.logs_fd.write((
                f'Migration skipped for container {name!r} because a container with the same name '
                f'already exists\n'
            ).encode())
            continue

        dst_dataset = os.path.join(container_dataset(pool), f'containers/{name}')
        needs_mount_revert = False
        renamed = False
        container_instance = None
        try:
            if not processed_parents_mountpoints:
                # Armed before the properties are touched, for the same reason the
                # per-container revert is: this flag also decides whether the parents
                # get restored at the end, and the first of the two can be applied
                # before the second one fails.
                processed_parents_mountpoints = True
                for ds in (f'{pool}/.ix-virt', f'{pool}/.ix-virt/containers'):
                    context.middleware.call_sync(
                        'pool.dataset.update_impl',
                        UpdateImplArgs(
                            name=ds,
                            zprops={'readonly': 'off'},
                            iprops={'mountpoint'}
                        )
                    )

            # Armed before the properties are touched: a partial apply has to be
            # reverted too, and update_impl can fail between the two of them.
            needs_mount_revert = True
            context.middleware.call_sync(
                'pool.dataset.update_impl',
                UpdateImplArgs(
                    name=dataset['name'],
                    zprops={'canmount': 'on'},
                    iprops={'mountpoint'},
                )
            )
            context.call_sync2(context.s.zfs.resource.mount, dataset['name'])

            try:
                with open(f'/mnt/{dataset['name']}/backup.yaml') as f:
                    manifest = yaml.safe_load(f.read())
            except Exception:
                job.logs_fd.write(
                    f'Failed to read backup.yaml for container {name!r}, skipping.\n'.encode()
                )
                continue

            # Relocate the origin image out of .ix-virt before renaming the container
            # into .truenas_containers, so a later deletion of .ix-virt cannot cascade
            # into the migrated container. This runs only once the dataset is known to
            # be a real container: an image kept alive solely by a leftover clone that
            # is not one stays inside .ix-virt and is reclaimed along with it.
            if relocate_container_origin(context, dataset['name']) in ('FAILED', 'ABSENT'):
                # Skip it. Migrating a container whose origin is still inside .ix-virt
                # would produce something that looks healthy right up until .ix-virt is
                # deleted and takes it with it; leaving it untouched keeps it whole.
                job.logs_fd.write((
                    f'Skipping container {name!r}: could not relocate its base image out of .ix-virt.\n'
                ).encode())
                continue

            config = manifest['container']['config']

            # Move rootfs contents to parent dataset for compatibility with current implementation
            rootfs_path = f'/mnt/{dataset['name']}/rootfs'
            parent_path = f'/mnt/{dataset['name']}'
            with os.scandir(rootfs_path) as entries:
                for entry in entries:
                    os.rename(entry.path, os.path.join(parent_path, entry.name))

            rootfs_stats = os.stat(rootfs_path)
            os.chmod(parent_path, rootfs_stats.st_mode)
            os.chown(parent_path, rootfs_stats.st_uid, rootfs_stats.st_gid)
            os.rmdir(rootfs_path)

            context.call_sync2(context.s.zfs.resource.rename, dataset['name'], dst_dataset)
            # From here on the dataset lives in its native location, where the mount
            # properties set above are the correct ones to keep.
            needs_mount_revert = False
            renamed = True

            container_instance = context.call_sync2(
                context.s.container.create_with_dataset, ContainerCreateWithDataset(
                    name=name,
                    autostart=config.get('user.autostart') == 'true',
                    dataset=dst_dataset,
                    init='/sbin/init',
                    cpuset=config.get('limits.cpu', None),
                )
            )
            existing_containers.append(name)
            context.run_coroutine(migrate_devices(context, job, manifest['container'], container_instance))
        except Exception as e:
            if renamed and container_instance is None:
                # The dataset was moved but no container row was created. Left there it
                # is invisible: the migration only ever looks under .ix-virt, and the
                # native tree is hidden from dataset queries. Move it back so it stays
                # something the user can see and act on.
                try:
                    context.call_sync2(context.s.zfs.resource.rename, dst_dataset, dataset['name'])
                except Exception:
                    context.logger.error(
                        '%s: failed to move back after an incomplete migration', dst_dataset,
                        exc_info=True,
                    )
                else:
                    needs_mount_revert = True

            context.logger.error('Unable to migrate container %r', name, exc_info=True)
            job.logs_fd.write(f'Unable to migrate container {name!r}: {e!r}.\n'.encode())
        else:
            job.logs_fd.write(f'Successfully migrated container {name!r}.\n'.encode())
        finally:
            if needs_mount_revert:
                revert_incus_mount_properties(context, job, dataset['name'])

    if processed_parents_mountpoints:
        restore_legacy_parent_mountpoints(context, pool)


def revert_incus_mount_properties(context: ServiceContext, job: Job, container_ds: str) -> None:
    """Restore the mount properties incus set on a container dataset that stays put.

    Inspecting a legacy container means mounting it, which means replacing the
    ``canmount=noauto``/``mountpoint=legacy`` pair incus relies on with a real
    mountpoint. A container that is not migrated must not keep that: it would be
    left mounted under ``/mnt/<pool>/.ix-virt`` and remounted on every boot, with
    nothing left on the system that manages it.
    """
    assert job.logs_fd is not None
    try:
        context.call_sync2(context.s.zfs.resource.unmount, container_ds)
    except Exception:
        context.logger.warning(
            '%s: failed to unmount after skipping migration', container_ds, exc_info=True,
        )
        job.logs_fd.write(f'Failed to unmount {container_ds!r} after skipping it.\n'.encode())

    try:
        context.middleware.call_sync(
            'pool.dataset.update_impl',
            UpdateImplArgs(
                name=container_ds,
                zprops={'canmount': 'noauto', 'mountpoint': 'legacy'},
            ),
        )
    except Exception:
        context.logger.warning(
            '%s: failed to restore mount properties after skipping migration',
            container_ds, exc_info=True,
        )
        job.logs_fd.write(
            f'Failed to restore mount properties on {container_ds!r} after skipping it.\n'.encode()
        )


def restore_legacy_parent_mountpoints(context: ServiceContext, pool: str) -> None:
    """Put the legacy parent datasets back the way incus had them.

    Migrating a container needs its parents mounted, so they are given an inherited
    mountpoint. Leaving them that way keeps the whole legacy tree mounted under
    ``/mnt/<pool>/.ix-virt`` for good, even on a run where nothing was migrated.
    Children first, so the parent is not unmounted out from under one of them.
    """
    for ds in (f'{pool}/.ix-virt/containers', f'{pool}/.ix-virt'):
        try:
            context.middleware.call_sync(
                'pool.dataset.update_impl',
                UpdateImplArgs(name=ds, zprops={'mountpoint': 'legacy'}),
            )
        except Exception:
            context.logger.warning('%s: failed to restore mountpoint after migration', ds, exc_info=True)


def relocate_container_origin(context: ServiceContext, container_ds: str) -> str:
    """Relocate a migrated container's origin image out of legacy ``.ix-virt``.

    A migrated container is a ZFS clone whose ``origin`` snapshot may still
    live inside ``<pool>/.ix-virt``. A recursive destroy of ``.ix-virt``
    cascades into dependent clones regardless of where they live, so such a
    container is destroyed if the user later deletes ``.ix-virt``. This moves
    the origin image dataset into the native ``<pool>/.truenas_containers/images``
    tree so the container no longer depends on anything under ``.ix-virt``.

    Best-effort. Returns one of:
      - ``RELOCATED``: the origin image was moved.
      - ``ALREADY_SATISFIED``: not a clone, or the origin already lives
        outside ``.ix-virt`` (a fan-out sibling or earlier run moved it);
        the caller may proceed.
      - ``FAILED``: could not relocate; the container still depends on
        something inside ``.ix-virt``, or it is a clone of another
        container rather than of an image.
      - ``ABSENT``: the container dataset (or its pool) is not present.
    """
    try:
        resources = context.call_sync2(
            context.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[container_ds], properties=['origin']),
        )
    except Exception:
        context.logger.error('%s: failed to read origin', container_ds, exc_info=True)
        return 'FAILED'

    if not resources:
        return 'ABSENT'

    origin = resources[0]['properties']['origin']['value']
    if origin in (None, '', 'none'):
        return 'ALREADY_SATISFIED'

    origin_dataset = origin.split('@')[0]
    pool = origin_dataset.split('/')[0]
    ix_virt = f'{pool}/.ix-virt/'
    if any(
        origin_dataset.startswith(f'{prefix}containers/')
        for prefix in (ix_virt, f'{container_dataset(pool)}/')
    ):
        # A container cloned from another container would arrive in the native tree
        # still linked to that sibling, and the two stay entangled: neither can be
        # removed without dealing with the snapshot the other hangs off. The sibling
        # may already have migrated, hence the native path.
        context.logger.warning(
            '%s: origin %r is another container; skipping relocation',
            container_ds, origin_dataset,
        )
        return 'FAILED'

    if not origin_dataset.startswith(ix_virt):
        # Already relocated (fan-out sibling / prior run) or never in .ix-virt.
        return 'ALREADY_SATISFIED'

    if not (
        origin_dataset.startswith(f'{ix_virt}images/')
        or origin_dataset.startswith(f'{ix_virt}deleted/images/')
    ):
        # Via the supported API a container origin is always an image
        # snapshot. Anything else under .ix-virt is only reachable through
        # the raw incus CLI, which we make no promises about.
        context.logger.warning(
            '%s: origin %r is under .ix-virt but is not an image dataset; skipping relocation',
            container_ds, origin_dataset,
        )
        return 'FAILED'

    context.run_coroutine(ensure_datasets(context, pool))

    fingerprint = origin_dataset.rsplit('/', 1)[1]
    target = os.path.join(container_dataset(pool), f'images/{fingerprint}')

    # EEXIST-tolerance: the same fingerprint can, in crash/manual states,
    # exist under both images/ and deleted/images/. Same fingerprint means
    # identical content, so an extra copy is only redundant disk - pick a
    # free name rather than failing.
    final_target = target
    attempt = 0
    while context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[final_target], properties=None),
    ):
        attempt += 1
        final_target = f'{target}-migrated-{attempt}'

    # canmount is set before the rename so the atomic rename is the last step:
    # either the image is still wholly in .ix-virt, or it is fully relocated.
    try:
        context.middleware.call_sync(
            'pool.dataset.update_impl',
            UpdateImplArgs(name=origin_dataset, zprops={'canmount': 'noauto'}),
        )
        context.call_sync2(context.s.zfs.resource.rename, origin_dataset, final_target)
    except Exception:
        context.logger.error(
            '%s: failed to relocate origin image %r out of .ix-virt',
            container_ds, origin_dataset, exc_info=True,
        )
        return 'FAILED'

    return 'RELOCATED'
