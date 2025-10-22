import os
from collections import defaultdict
from dataclasses import dataclass
from packaging.version import Version

from middlewared.plugins.catalog.utils import IX_APP_NAME

from .docker.query import list_resources_by_project
from .metadata import get_collective_config, get_collective_metadata
from .lifecycle import get_current_app_config
from .path import get_app_parent_config_path
from .utils import AppState, ContainerState, get_app_name_from_project_name, normalize_reference, PROJECT_PREFIX


COMPOSE_SERVICE_KEY: str = 'com.docker.compose.service'


@dataclass(frozen=True, eq=True)
class VolumeMount:
    source: str
    destination: str
    mode: str
    type: str

    def __hash__(self):
        return hash((self.source, self.destination, self.type))


def upgrade_available_for_app(
    version_mapping: dict[str, dict[str, dict[str, str]]], app_metadata: dict, image_updates_available: bool = False,
) -> tuple[bool, str | None]:
    # TODO: Eventually we would want this to work as well but this will always require middleware changes
    #  depending on what new functionality we want introduced for custom app, so let's take care of this at that point
    catalog_app_metadata = app_metadata['metadata']
    catalog_app = catalog_app_metadata['name']
    if app_metadata['custom_app'] is False and version_mapping.get(
        catalog_app_metadata['train'], {}
    ).get(catalog_app_metadata['name']):
        latest_version = version_mapping[catalog_app_metadata['train']][catalog_app_metadata['name']]['version']
        return Version(catalog_app_metadata['version']) < Version(
            latest_version
        ), latest_version
    elif (app_metadata['custom_app'] or catalog_app == IX_APP_NAME) and image_updates_available:
        return True, None
    else:
        return False, None


def normalize_portal_uri(portal_uri: str, host_ip: str | None) -> str:
    if not host_ip or '0.0.0.0' not in portal_uri:
        return portal_uri

    if ':' in host_ip and '[' not in host_ip:
        # We already have ipv6 normalized but users who are using older apps before we had ipv6 support,
        # will have this not normalized and can run into this so we should fix this here to be safe
        host_ip = f'[{host_ip}]'

    return portal_uri.replace('0.0.0.0', host_ip)


def get_config_of_app(app_data: dict, collective_config: dict, retrieve_config: bool) -> dict:
    return {
        'config': collective_config.get(app_data['name']) or (
            get_current_app_config(app_data['name'], app_data['version']) if app_data['version'] else {}
        )
    } if retrieve_config else {}


def normalize_portal_uris(portals: dict[str, str], host_ip: str | None) -> dict[str, str]:
    return {name: normalize_portal_uri(uri, host_ip) for name, uri in portals.items()}


def create_external_app_metadata(app_name: str, container_details: list[dict]) -> dict:
    """
    Create synthetic metadata for external Docker containers not managed by TrueNAS.
    """
    # Get the primary image from the first container
    primary_image = container_details[0]['image'] if container_details else 'unknown'

    return {
        'metadata': {
            'name': app_name,
            'title': app_name,
            'description': f'External Docker container: {app_name}',
            'app_version': 'N/A',
            'version': '1.0.0',
            'train': 'external',
            'icon': '',
            'categories': ['external'],
            'capabilities': [],
            'host_mounts': [],
            'keywords': [],
            'home': '',
            'sources': [],
            'screenshots': [],
            'maintainers': [],
            'run_as_context': [],
            'lib_version': '',
            'lib_version_hash': '',
            'last_update': '',
        },
        'version': '1.0.0',
        'human_version': primary_image,
        'portals': {},
        'notes': f'This is an external container deployed outside of TrueNAS Apps. Image: {primary_image}',
        'custom_app': True,
        'migrated': False,
        'source': 'external',
    }


def list_apps(
    train_to_apps_version_mapping: dict[str, dict[str, dict[str, str]]],
    specific_app: str | None = None,
    host_ip: str | None = None,
    retrieve_config: bool = False,
    image_update_cache: dict | None = None,
    include_external: bool = False,
) -> list[dict]:
    apps = []
    image_update_cache = image_update_cache or {}
    app_names = set()
    metadata = get_collective_metadata()
    collective_config = get_collective_config() if retrieve_config else {}
    # This will only give us apps which are running or in deploying state
    for app_name, app_resources in list_resources_by_project(
        project_name=f'{PROJECT_PREFIX}{specific_app}' if specific_app else None,
        include_external=include_external,
    ).items():
        # Determine if this is a TrueNAS app or external app
        is_truenas_app = app_name.startswith(PROJECT_PREFIX)
        app_name = get_app_name_from_project_name(app_name) if is_truenas_app else app_name
        app_names.add(app_name)

        # Get workloads first to have container details for external apps
        workloads = translate_resources_to_desired_workflow(app_resources)

        # Handle missing metadata
        if app_name not in metadata:
            if is_truenas_app:
                # TrueNAS apps without metadata are malformed
                continue
            else:
                # External apps - create synthetic metadata
                app_metadata = create_external_app_metadata(app_name, workloads['container_details'])
        else:
            app_metadata = metadata[app_name]
        # When we stop docker service and start it again - the containers can be in exited
        # state which means we need to account for this.
        state = AppState.STOPPED
        workload_stats = defaultdict(int)
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

        state = state.value

        active_workloads = get_default_workload_values() if state == 'STOPPED' else workloads
        image_updates_available = any(
            image_update_cache.get(normalize_reference(k)['complete_tag']) for k in active_workloads['images']
        )
        upgrade_available, latest_version = upgrade_available_for_app(train_to_apps_version_mapping, app_metadata)

        # Determine app source
        app_source = app_metadata.get('source', 'truenas' if is_truenas_app else 'external')

        app_data = {
            'name': app_name,
            'id': app_name,
            'active_workloads': active_workloads,
            'state': state,
            'upgrade_available': upgrade_available,
            'latest_version': latest_version,
            'image_updates_available': image_updates_available,
            'source': app_source,
            **app_metadata | {'portals': normalize_portal_uris(app_metadata['portals'], host_ip)}
        }
        if (app_data['custom_app'] or app_metadata['metadata']['name'] == IX_APP_NAME) and image_updates_available:
            # We want to mark custom apps and ix-apps as upgrade available if image updates are available
            # so if user tries to upgrade, we will just be pulling a newer version of the image
            # against the same docker tag
            app_data['upgrade_available'] = True

        apps.append(app_data | get_config_of_app(app_data, collective_config, retrieve_config))

    if specific_app and specific_app in app_names:
        return apps

    # We should now retrieve apps which are in stopped state
    with os.scandir(get_app_parent_config_path()) as scan:
        for entry in filter(
            lambda e: e.is_dir() and ((specific_app and e.name == specific_app) or e.name not in app_names), scan
        ):
            app_names.add(entry.name)
            if entry.name not in metadata:
                # The app is malformed or something is seriously wrong with it
                continue

            app_metadata = metadata[entry.name]
            upgrade_available, latest_version = upgrade_available_for_app(train_to_apps_version_mapping, app_metadata)

            # Stopped apps from config path are TrueNAS apps
            app_data = {
                'name': entry.name,
                'id': entry.name,
                'active_workloads': get_default_workload_values(),
                'state': AppState.STOPPED.value,
                'upgrade_available': upgrade_available,
                'latest_version': latest_version,
                'image_updates_available': False,
                'source': app_metadata.get('source', 'truenas'),
                **app_metadata | {'portals': normalize_portal_uris(app_metadata['portals'], host_ip)}
            }
            apps.append(app_data | get_config_of_app(app_data, collective_config, retrieve_config))

    return apps


def get_default_workload_values() -> dict:
    return {
        'containers': 0,
        'used_ports': [],
        'used_host_ips': [],
        'container_details': [],  # This would contain service name and image in use
        'volumes': [],  # This would be docker volumes
        'images': [],
        'networks': [],
    }


def translate_resources_to_desired_workflow(app_resources: dict) -> dict:
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
        # External containers may not have Docker Compose labels
        service_name = container['Config']['Labels'].get(
            COMPOSE_SERVICE_KEY,
            container.get('Name', '').lstrip('/')
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

        if container['State']['Status'].lower() == 'running':
            if health_config := container['State'].get('Health'):
                if health_config['Status'] == 'healthy':
                    state = ContainerState.RUNNING.value
                else:
                    state = ContainerState.STARTING.value
            else:
                state = ContainerState.RUNNING.value
        elif container['State']['Status'].lower() == 'created':
            state = ContainerState.CREATED.value
        elif container['State']['Status'] == 'exited' and container['State']['ExitCode'] != 0:
            state = ContainerState.CRASHED.value
        else:
            state = 'exited'

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
