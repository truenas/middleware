import contextlib
import errno
import os
import shutil
import uuid

from datetime import datetime

from middlewared.api.current import ZFSResourceQuery
from middlewared.service import CallError, ServiceContext
from middlewared.utils.interface import wait_for_default_interface_link_state_up
from middlewared.plugins.pool_.utils import CreateImplArgs, UpdateImplArgs

from .fs_manage import mount_docker_ds
from .state_management import start_service, periodic_check
from .state_utils import (
    DatasetDefaults, DOCKER_DATASET_NAME, docker_datasets, IX_APPS_MOUNT_PATH, missing_required_datasets,
)


async def status_change(context: ServiceContext) -> None:
    config = await context.call2(context.s.docker.config)
    if not config.pool:
        try:
            await (await context.call2(context.s.catalog.sync)).wait()  # type: ignore[call-overload,misc]
        except CallError as e:
            if e.errno != errno.EBUSY:
                raise
        return

    assert config.dataset is not None
    await context.to_thread(create_update_docker_datasets, context, config.dataset)
    # Docker dataset would not be mounted at this point, so we will explicitly mount them now
    catalog_sync_job = await mount_docker_ds(context)
    if catalog_sync_job:
        await catalog_sync_job.wait()

    await start_service(context)
    context.create_task(periodic_check(context))


async def validate_fs(context: ServiceContext) -> None:
    config = await context.call2(context.s.docker.config)
    if not config.pool:
        raise CallError(f'{config.pool!r} pool not found.')

    assert config.dataset is not None
    ds = {
        i['name']
        for i in await context.call2(
            context.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=docker_datasets(config.dataset), properties=None)
        )
    }
    if missing_datasets := missing_required_datasets(ds, config.dataset):
        raise CallError(f'Missing "{", ".join(missing_datasets)}" dataset(s) required for starting docker.')

    await context.to_thread(create_update_docker_datasets, context, config.dataset)

    for i in (config.dataset, config.pool):
        if await context.middleware.call('pool.dataset.path_in_locked_datasets', i):
            raise CallError(
                f'Cannot start docker because {i!r} is located in a locked dataset.',
                errno=CallError.EDATASETISLOCKED,
            )

    # What we want to validate now is that the interface on default route is up and running
    # This is problematic for bridge interfaces which can or cannot come up in time
    await validate_interfaces(context)


def create_update_docker_datasets(context: ServiceContext, docker_ds: str) -> None:
    """
    The following logic applies:

        1. create the docker datasets fresh (if they dont exist)
        2. OR update the docker datasets zfs properties if they
            don't match reality.

        NOTE: this method needs to be optimized as much as possible
        since this is called on docker state change for each docker
        dataset
    """
    expected_docker_datasets = docker_datasets(docker_ds)
    actual_docker_datasets = {
        i['name']: i['properties'] for i in context.call_sync2(
            context.s.zfs.resource.query_impl,
            ZFSResourceQuery(
                paths=expected_docker_datasets,
                properties=list(DatasetDefaults.update_only(skip_ds_name_check=True).keys()),
            )
        )
    }
    for dataset_name in expected_docker_datasets:
        if existing_dataset := actual_docker_datasets.get(dataset_name):
            update_props = DatasetDefaults.update_only(os.path.basename(dataset_name))
            if any(val['raw'] != update_props[name] for name, val in existing_dataset.items()):
                # if any of the zfs properties don't match what we expect we'll update all properties
                context.middleware.call_sync(
                    'pool.dataset.update_impl',
                    UpdateImplArgs(name=dataset_name, zprops=update_props)
                )
        else:
            move_conflicting_dir(dataset_name)
            context.middleware.call_sync(
                'pool.dataset.create_impl',
                CreateImplArgs(
                    name=dataset_name,
                    ztype='FILESYSTEM',
                    zprops=DatasetDefaults.create_time_props(os.path.basename(dataset_name))
                )
            )


def move_conflicting_dir(ds_name: str) -> None:
    base_ds_name = os.path.basename(ds_name)
    from_path = os.path.join(IX_APPS_MOUNT_PATH, base_ds_name)
    if ds_name == DOCKER_DATASET_NAME:
        from_path = IX_APPS_MOUNT_PATH

    with contextlib.suppress(FileNotFoundError):
        # can't stop someone from manually creating same name
        # directories on disk so we'll just move them
        shutil.move(from_path, f'{from_path}-{str(uuid.uuid4())[:4]}-{datetime.now().isoformat()}')


async def validate_interfaces(context: ServiceContext) -> None:
    default_iface, success = await context.to_thread(wait_for_default_interface_link_state_up)
    if default_iface is None:
        raise CallError('Unable to determine default interface')
    elif not success:
        raise CallError(f'Default interface {default_iface!r} is not in active state')
