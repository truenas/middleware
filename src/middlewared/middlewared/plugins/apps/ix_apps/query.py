from collections import defaultdict
from dataclasses import dataclass
import os
from typing import Any

from packaging.version import Version

from middlewared.plugins.apps_images.utils import normalize_reference
from middlewared.plugins.catalog.utils import IX_APP_NAME

from .docker.query import list_resources_by_project
from .lifecycle import get_current_app_config
from .metadata import get_collective_config, get_collective_metadata, resolve_app_metadata
from .path import get_app_parent_config_path
from .utils import PROJECT_PREFIX, AppErrorReason, AppState, ContainerState, get_app_name_from_project_name

COMPOSE_SERVICE_KEY: str = 'com.docker.compose.service'
KNOWN_NORMAL_EXIT_CODES: tuple[int, ...] = (
    0,    # Normal exit
    129,  # SIGHUP
    130,  # SIGINT
    137,  # SIGKILL
    143,  # SIGTERM
)


@dataclass(frozen=True, eq=True)
class VolumeMount:
    source: str
    destination: str
    mode: str
    type: str

    def __hash__(self) -> int:
        return hash((self.source, self.destination, self.type))


def upgrade_available_for_app(
    version_mapping: dict[str, dict[str, dict[str, str | None]]],
    app_metadata: dict[str, Any],
    image_updates_available: bool = False,
) -> tuple[bool, str | None, str | None]:
    # TODO: Eventually we would want this to work as well but this will always require middleware changes
    #  depending on what new functionality we want introduced for custom app, so let's take care of this at that point
    catalog_app_metadata = app_metadata.get('metadata') or {}
    catalog_app = catalog_app_metadata.get('name')
    catalog_train = catalog_app_metadata.get('train')
    if (
        app_metadata.get('custom_app') is False
        # Corrupt metadata can hold anything at all here, including values yaml parsed as a
        # non-string, so these must be validated before they are used as lookup keys
        and isinstance(catalog_app, str)
        and isinstance(catalog_train, str)
        and catalog_app_metadata.get('version')
        and (
            latest_version_info := version_mapping.get(catalog_train, {}).get(catalog_app)
        )
        and latest_version_info['version']
    ):
        return (
            Version(catalog_app_metadata['version']) < Version(latest_version_info['version']),
            latest_version_info['version'],
            latest_version_info['app_version']
        )
    elif (app_metadata.get('custom_app') or catalog_app == IX_APP_NAME) and image_updates_available:
        return True, None, None
    else:
        return False, None, None


def normalize_portal_uri(portal_uri: str, host_ip: str | None) -> str:
    if not host_ip or '0.0.0.0' not in portal_uri:
        return portal_uri

    if ':' in host_ip and '[' not in host_ip:
        # We already have ipv6 normalized but users who are using older apps before we had ipv6 support,
        # will have this not normalized and can run into this so we should fix this here to be safe
        host_ip = f'[{host_ip}]'

    return portal_uri.replace('0.0.0.0', host_ip)


def get_config_of_app(
    app_data: dict[str, Any], collective_config: dict[str, Any], retrieve_config: bool,
) -> dict[str, Any]:
    if retrieve_config:
        return {
            'config': collective_config.get(app_data['name']) or (
                get_current_app_config(app_data['name'], app_data['version']) if app_data['version'] else {}
            )
        }
    else:
        return {'config': None}


def normalize_portal_uris(portals: dict[str, str], host_ip: str | None) -> dict[str, str]:
    return {name: normalize_portal_uri(uri, host_ip) for name, uri in portals.items()}


def error_app_data(
    app_name: str, error_reason: AppErrorReason, workloads: dict[str, Any], retrieve_config: bool,
) -> dict[str, Any]:
    """
    Entry for an app whose on-disk metadata is unusable. Everything we would normally read out of
    that metadata is reported as unknown rather than guessed at.
    """
    return {
        'name': app_name,
        'id': app_name,
        'active_workloads': workloads,
        'state': AppState.ERROR.value,
        'error_reason': error_reason,
        'upgrade_available': False,
        'latest_version': None,
        'latest_app_version': None,
        'image_updates_available': False,
        'action_required': False,
        'custom_app': False,
        'migrated': False,
        'human_version': None,
        'version': None,
        'metadata': {},
        'portals': {},
        'notes': None,
        'version_details': None,
        'config': {} if retrieve_config else None,
    }


def list_apps(
    train_to_apps_version_mapping: dict[str, dict[str, dict[str, str | None]]],
    specific_app: str | None = None,
    host_ip: str | None = None,
    retrieve_config: bool = False,
    image_update_cache: dict[str, Any] | None = None,
    installing: set[str] | None = None,
) -> list[dict[str, Any]]:
    apps = []
    installing = installing or set()
    image_update_cache = image_update_cache or {}
    app_names = set()
    metadata = get_collective_metadata()
    collective_config = get_collective_config() if retrieve_config else {}
    # This will only give us apps which are running or in deploying state
    for app_name, app_resources in list_resources_by_project(
        project_name=f'{PROJECT_PREFIX}{specific_app}' if specific_app else None,
    ).items():
        app_name = get_app_name_from_project_name(app_name)
        app_names.add(app_name)
        app_metadata, error_reason, present = resolve_app_metadata(app_name, metadata, True, installing)
        if not present:
            continue

        workloads = translate_resources_to_desired_workflow(app_resources)
        if error_reason is not None:
            # Report the app's real workloads so that the ports and volumes it is still holding on to
            # remain visible to conflict checks, even though we know nothing else about it
            apps.append(error_app_data(app_name, error_reason, workloads, retrieve_config))
            continue

        # When we stop docker service and start it again - the containers can be in exited
        # state which means we need to account for this.
        state = AppState.STOPPED
        workload_stats: defaultdict[str, int] = defaultdict(int)
        workloads_len = len(workloads['container_details'])
        for container in workloads['container_details']:
            workload_stats[container['state']] += 1

        if workload_stats[ContainerState.CRASHED.value]:
            state = AppState.CRASHED
        elif workload_stats[ContainerState.CREATED.value] or workload_stats[ContainerState.STARTING.value]:
            state = AppState.DEPLOYING
        elif 0 < workloads_len == sum(
            workload_stats[k.value] for k in (ContainerState.RUNNING, ContainerState.EXITED)
        ) and workload_stats[ContainerState.RUNNING.value]:
            state = AppState.RUNNING

        state_value: str = state.value

        active_workloads = get_default_workload_values() if state_value == 'STOPPED' else workloads
        image_updates_available = any(
            image_update_cache.get(normalize_reference(k)['complete_tag']) for k in active_workloads['images']
        )
        upgrade_available, latest_version, latest_app_version = upgrade_available_for_app(
            train_to_apps_version_mapping, app_metadata
        )
        app_data = {
            'name': app_name,
            'id': app_name,
            'active_workloads': active_workloads,
            'state': state_value,
            'upgrade_available': upgrade_available,
            'latest_version': latest_version,
            'action_required': False,
            'latest_app_version': latest_app_version,
            'image_updates_available': image_updates_available,
            'error_reason': None,
            'version_details': None,
            **app_metadata | {'portals': normalize_portal_uris(app_metadata.get('portals') or {}, host_ip)}
        }
        if (
            app_data.get('custom_app') or (app_metadata.get('metadata') or {}).get('name') == IX_APP_NAME
        ) and image_updates_available:
            # We want to mark custom apps and ix-apps as upgrade available if image updates are available
            # so if user tries to upgrade, we will just be pulling a newer version of the image
            # against the same docker tag
            app_data['upgrade_available'] = True

        apps.append(app_data | get_config_of_app(app_data, collective_config, retrieve_config))

    if specific_app and specific_app in app_names:
        return apps

    # We should now retrieve apps which are in stopped state
    try:
        with os.scandir(get_app_parent_config_path()) as scan:
            for entry in filter(
                lambda e: e.is_dir() and ((specific_app and e.name == specific_app) or e.name not in app_names), scan
            ):
                app_names.add(entry.name)
                app_metadata, error_reason, present = resolve_app_metadata(entry.name, metadata, False, installing)
                if not present:
                    continue

                if error_reason is not None:
                    apps.append(error_app_data(
                        entry.name, error_reason, get_default_workload_values(), retrieve_config,
                    ))
                    continue

                upgrade_available, latest_version, latest_app_version = upgrade_available_for_app(
                    train_to_apps_version_mapping, app_metadata
                )
                app_data = {
                    'name': entry.name,
                    'id': entry.name,
                    'active_workloads': get_default_workload_values(),
                    'state': AppState.STOPPED.value,
                    'upgrade_available': upgrade_available,
                    'latest_version': latest_version,
                    'action_required': False,
                    'latest_app_version': latest_app_version,
                    'image_updates_available': False,
                    'error_reason': None,
                    'version_details': None,
                    **app_metadata | {'portals': normalize_portal_uris(app_metadata.get('portals') or {}, host_ip)}
                }
                apps.append(app_data | get_config_of_app(app_data, collective_config, retrieve_config))
    except FileNotFoundError:
        # Observed in failed CI runs. It's possible that .ix-apps fails to mount properly
        # we don't want to crash here since it'll cause many operations to fail (including pool export).
        pass

    return apps


def get_default_workload_values() -> dict[str, Any]:
    return {
        'containers': 0,
        'used_ports': [],
        'used_host_ips': [],
        'container_details': [],  # This would contain service name and image in use
        'volumes': [],  # This would be docker volumes
        'images': [],
        'networks': [],
    }


def translate_resources_to_desired_workflow(app_resources: dict[str, Any]) -> dict[str, Any]:
    # We are looking for following data points
    # No of containers
    # Used ports
    # Networks
    # Volumes
    # Container mounts
    workloads = get_default_workload_values()
    volumes = set()
    images = set()
    host_ips = set()
    workloads['containers'] = len(app_resources['containers'])
    for container in app_resources['containers']:
        service_name = (
            container['Config']['Labels'].get(COMPOSE_SERVICE_KEY)
            or container.get('Name', '').lstrip('/')
            or 'unknown'
        )
        container_ports_config = []
        images.add(container['Config']['Image'])
        for container_port, host_config in container.get('NetworkSettings', {}).get('Ports', {}).items():
            if not host_config:
                # This will happen for ports which are not exposed on the host side
                continue
            host_ports = []
            for host_port in host_config:
                try:
                    # We have seen that docker can report host port as an empty string or null
                    host_ip = host_port['HostIp']
                    host_ports.append({'host_port': int(host_port['HostPort']), 'host_ip': host_ip})
                    if host_ip:
                        host_ips.add(host_ip)
                except (TypeError, ValueError):
                    continue

            port_config = {
                'container_port': int(container_port.split('/')[0]),
                'protocol': container_port.split('/')[1],
                'host_ports': host_ports,
            }
            container_ports_config.append(port_config)

        volume_mounts = []
        for volume_mount in container.get('Mounts', []):
            volume_mounts.append(VolumeMount(
                source=volume_mount['Source'],
                destination=volume_mount['Destination'],
                mode=volume_mount['Mode'],
                type='bind' if volume_mount['Type'] == 'bind' else 'volume',
            ))

        container_status = container['State']['Status'].lower()
        if container_status == 'running':
            if health_config := container['State'].get('Health'):
                if health_config['Status'] == 'healthy':
                    state = ContainerState.RUNNING.value
                else:
                    state = ContainerState.STARTING.value
            else:
                state = ContainerState.RUNNING.value
        elif container_status == 'created':
            state = ContainerState.CREATED.value
        elif container_status == 'exited' and container['State']['ExitCode'] not in KNOWN_NORMAL_EXIT_CODES:
            state = ContainerState.CRASHED.value
        else:
            state = ContainerState.EXITED.value

        workloads['container_details'].append({
            'service_name': service_name,
            'image': container['Config']['Image'],
            'port_config': container_ports_config,
            'state': state,
            'volume_mounts': [v.__dict__ for v in volume_mounts],
            'id': container['Id'],
        })
        workloads['used_ports'].extend(container_ports_config)
        volumes.update(volume_mounts)

    workloads.update({
        'images': list(images),
        'volumes': [v.__dict__ for v in volumes],
        'networks': app_resources['networks'],
        'used_host_ips': list(host_ips),
    })
    return workloads
