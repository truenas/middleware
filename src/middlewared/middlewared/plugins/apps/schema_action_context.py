from __future__ import annotations

import os
import typing

from middlewared.api.current import ZFSResourceQuery
from middlewared.service import CallError, ServiceContext
from middlewared.plugins.pool_.utils import CreateImplArgs

from .ix_apps.path import get_app_parent_volume_ds_name
from .utils import DatasetDefaults


async def update_volumes(context: ServiceContext, app_name: str, volumes: list[dict[str, typing.Any]]) -> None:
    docker_ds = (await context.call2(context.s.docker.config)).dataset
    if docker_ds is None:
        raise CallError('Docker dataset must not be null')

    app_volume_ds = get_app_parent_volume_ds_name(docker_ds, app_name)

    user_wants = {app_volume_ds: {'properties': {}}} | {os.path.join(app_volume_ds, v['name']): v for v in volumes}
    existing_datasets = {
        d['name'] for d in await context.call2(
            context.s.zfs.resource.query_impl, ZFSResourceQuery(paths=list(user_wants), properties=None)
        )
    }
    for create_ds in sorted(set(user_wants) - existing_datasets):
        await context.middleware.call(
            'pool.dataset.create_impl',
            CreateImplArgs(
                name=create_ds,
                ztype='FILESYSTEM',
                zprops=user_wants[create_ds]['properties'] | DatasetDefaults.create_time_props(),
            )
        )
        await context.call2(context.s.zfs.resource.mount, create_ds)


async def apply_acls(context: ServiceContext, acls_to_apply: dict[str, str]) -> None:
    bulk_job = await context.middleware.call(
        'core.bulk', 'filesystem.add_to_acl', [[acls_to_apply[acl_path]] for acl_path in acls_to_apply],
    )
    await bulk_job.wait()

    failures = []
    for status, acl_path in zip(bulk_job.result, acls_to_apply):
        if status['error']:
            failures.append((acl_path, status['error']))

    if failures:
        err_str = 'Failed to apply ACLs to the following paths: \n'
        for index, entry in enumerate(failures):
            err_str += f'{index + 1}) {entry[0]}: {entry[1]}\n'
        raise CallError(err_str)
