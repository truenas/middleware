from __future__ import annotations

import errno
import typing

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.service import CallError, ServiceContext, ValidationError

from .state_utils import docker_dataset_custom_props, IX_APPS_MOUNT_PATH, Status


if typing.TYPE_CHECKING:
    from middlewared.job import Job


async def ensure_ix_apps_mount_point(context: ServiceContext, docker_ds: str) -> None:
    """
    Ensure ix-apps dataset is mounted at /mnt/.ix-apps and update it accordingly.

    This is helpful in the event when user rolled back to a previous version of TN
    where docker apps were not supported, what happens here is that the mountpoint of
    ix-apps dataset is reset and it gets mounted under root dataset. Now when he comes back
    to newer TN version, we need to update the mount point of ix-apps dataset so it gets reflected
    properly.
    """
    ds = await context.call2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[docker_ds], properties=['mountpoint'])
    )
    if not ds:
        return

    # If the mount point is not at the expected location, fix it
    if ds[0]['properties']['mountpoint']['value'] != IX_APPS_MOUNT_PATH:
        mp = docker_dataset_custom_props(docker_ds.split('/')[-1])['mountpoint']
        await context.middleware.call(
            'pool.dataset.update_impl',
            UpdateImplArgs(name=docker_ds, zprops={'mountpoint': mp})
        )


async def ix_apps_is_mounted(context: ServiceContext, dataset_to_check: str | None = None) -> bool:
    """
    This will tell us if some dataset is mounted on /mnt/.ix-apps or not.
    """
    try:
        fs_details = await context.middleware.call('filesystem.statfs', IX_APPS_MOUNT_PATH)
    except CallError as e:
        if e.errno == errno.ENOENT:
            return False
        raise

    if fs_details['source'].startswith('boot-pool/'):
        return False

    if dataset_to_check:
        return bool(fs_details['source'] == dataset_to_check)

    return True


async def common_func(context: ServiceContext, mount: bool) -> Job | None:
    docker_ds = (await context.call2(context.s.docker.config)).dataset
    if not docker_ds:
        return None

    try:
        if mount:
            # Ensure ix-apps has correct mountpoint set
            await ensure_ix_apps_mount_point(context, docker_ds)
            await context.call2(
                context.s.zfs.resource.mount,
                docker_ds,
                recursive=True,
                force=True,
            )
        else:
            try:
                await context.call2(
                    context.s.zfs.resource.unmount,
                    docker_ds,
                    recursive=True,
                    force=True
                )
            except ValidationError as e:
                if e.errno == errno.ENOENT:
                    # who cares, failing here is not ideal
                    # but it just means the underlying zfs
                    # dataset that houses the apps stuff is
                    # gone. if we crash here, we prevent users
                    # from using our API to move zpools that
                    # have the system dataset....dont do that
                    return None
                raise

            await context.middleware.call(
                'pool.dataset.update_impl',
                UpdateImplArgs(name=docker_ds, iprops={'mountpoint'})
            )
        try:
            return await context.middleware.call('catalog.sync')  # type: ignore[no-any-return]
        except CallError as e:
            if e.errno != errno.EBUSY:
                raise
            # A sync is already running - return that job so callers can wait on it
            if jobs := await context.middleware.call(
                'core.get_jobs', [['method', '=', 'catalog.sync'], ['state', '=', 'RUNNING']]
            ):
                return await context.middleware.call('core.job_wait', jobs[0]['id'])  # type: ignore[no-any-return]
    except Exception as e:
        await context.call2(
            context.s.docker.set_status, Status.FAILED.value,
            f'Failed to {"mount" if mount else "umount"} {docker_ds!r}: {e}',
        )
        raise

    return None


async def mount_docker_ds(context: ServiceContext) -> Job | None:
    return await common_func(context, True)


async def umount_docker_ds(context: ServiceContext) -> Job | None:
    # Wait for any running catalog.sync job before unmounting.
    # A running sync determines its target path at start - if it started
    # while mounted, it writes to /mnt/.ix-apps/truenas_catalog. Unmounting
    # while sync is active would cause writes to an invalid path.
    for job in await context.middleware.call(
        'core.get_jobs', [['method', '=', 'catalog.sync'], ['state', '=', 'RUNNING']]
    ):
        await (await context.middleware.call('core.job_wait', job['id'])).wait()

    return await common_func(context, False)
