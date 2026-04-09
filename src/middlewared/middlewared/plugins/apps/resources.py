from __future__ import annotations

import contextlib
import shutil
from collections import defaultdict
from typing import Any

from truenas_pylibvirt.utils.gpu import get_nvidia_gpus

from middlewared.api.current import (
    AppCertificate, AppCertificateChoices, AppContainerIDOptions, AppContainerResponse,
    AppGPUResponse, AppIpChoices, ContainerDetails, GPU, QueryOptions, ZFSResourceQuery,
)
from middlewared.plugins.zfs_.utils import paths_to_datasets_impl
from middlewared.service import ServiceContext

from .compose_utils import compose_action
from .crud import query_apps  # FIXME: Remove this dep
from .ix_apps.path import get_app_parent_volume_ds, get_installed_app_path
from .ix_apps.utils import ContainerState
from .resources_utils import get_normalized_gpu_choices
from .utils import IX_APPS_MOUNT_PATH


async def container_ids(
    context: ServiceContext, app_name: str, options: AppContainerIDOptions,
) -> AppContainerResponse:
    app = await context.call2(context.s.app.get_instance, app_name)
    return AppContainerResponse(root={
        c.id: ContainerDetails(
            id=c.id,
            service_name=c.service_name,
            image=c.image,
            state=c.state,
        ) for c in app.active_workloads.container_details if (
            options.alive_only is False or ContainerState(c.state) == ContainerState.RUNNING
        )
    })


async def container_console_choices(context: ServiceContext, app_name: str) -> AppContainerResponse:
    return await container_ids(context, app_name, AppContainerIDOptions(alive_only=True))


async def certificate_choices(context: ServiceContext) -> AppCertificateChoices:
    return [
        AppCertificate(**cert) for cert in await context.middleware.call(
            'certificate.query',
            [['cert_type_CSR', '=', False], ['cert_type_CA', '=', False], ['parsed', '=', True]],
            {'select': ['name', 'id']},
        )
    ]


async def used_ports(context: ServiceContext) -> list[int]:
    return sorted(list(set({
        host_port.host_port
        for app in query_apps(context, [], QueryOptions())
        for port_entry in app.active_workloads.used_ports
        for host_port in port_entry.host_ports
    })))


async def used_host_ips(context: ServiceContext) -> dict[str, list[str]]:
    app_ip_info: dict[str, list[str]] = defaultdict(list)
    for app in query_apps(context, [], QueryOptions()):
        for host_ip in app.active_workloads.used_host_ips:
            app_ip_info[host_ip].append(app.name)

    return dict(app_ip_info)


async def ip_choices(context: ServiceContext) -> AppIpChoices:
    return {
        ip['address']: ip['address']
        for ip in await context.middleware.call('interface.ip_in_use', {'static': True, 'any': True})
    }


async def available_space(context: ServiceContext) -> int:
    await context.call2(context.s.docker.validate_state)
    return (await context.middleware.call('filesystem.statfs', IX_APPS_MOUNT_PATH))['avail_bytes']


async def gpu_choices(context: ServiceContext) -> AppGPUResponse:
    return AppGPUResponse(root={
        gpu['pci_slot']: GPU(
            vendor=gpu['vendor'],
            description=gpu['description'],
            vendor_specific_config=gpu['vendor_specific_config'],
            pci_slot=gpu['pci_slot'],
            error=gpu['error'],
            gpu_details=gpu['gpu_details'],
        )
        for gpu in await gpu_choices_internal(context)
        if not gpu['error']
    })


async def gpu_choices_internal(context: ServiceContext) -> list[dict[str, Any]]:
    return get_normalized_gpu_choices(
        await context.middleware.call('device.get_gpus'),
        await context.middleware.run_in_thread(get_nvidia_gpus),
    )


async def get_hostpaths_datasets(context: ServiceContext, app_name: str) -> dict[str, str]:
    app_info = await context.call2(context.s.app.get_instance, app_name)
    host_paths = [
        volume.source for volume in app_info.active_workloads.volumes
        if volume.source.startswith(f'{IX_APPS_MOUNT_PATH}/') is False
    ]

    return await context.middleware.run_in_thread(paths_to_datasets_impl, host_paths)


def get_app_volume_ds(context: ServiceContext, app_name: str) -> str | None:
    # This will return volume dataset of app if it exists, otherwise null
    docker_ds = context.call_sync2(context.s.docker.config).dataset
    apps_volume_ds = get_app_parent_volume_ds(docker_ds, app_name)
    rv = context.call_sync2(
        context.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[apps_volume_ds], properties=None)
    )
    if rv:
        return rv[0]['name']
    return None


def remove_failed_resources(context: ServiceContext, app_name: str, version: str, remove_ds: bool = False) -> None:
    apps_volume_ds = get_app_volume_ds(context, app_name) if remove_ds else None

    with contextlib.suppress(Exception):
        compose_action(app_name, version, 'down', remove_orphans=True)

    shutil.rmtree(get_installed_app_path(app_name), ignore_errors=True)

    if apps_volume_ds and remove_ds:
        try:
            context.call_sync2(context.s.zfs.resource.destroy_impl, apps_volume_ds, recursive=True, bypass=True)
        except Exception:
            context.logger.error('Failed to remove %r app volume dataset', apps_volume_ds, exc_info=True)

    context.call_sync2(context.s.app.metadata_generate).wait_sync(raise_error=True)
    context.middleware.send_event('app.query', 'REMOVED', id=app_name)
