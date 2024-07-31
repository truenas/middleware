import os
from dataclasses import dataclass
from pkg_resources import parse_version

from .docker.query import list_resources_by_project
from .metadata import get_collective_config, get_collective_metadata
from .lifecycle import get_current_app_config
from .path import get_app_parent_config_path
from .utils import PROJECT_PREFIX


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
    version_mapping: dict[str, dict[str, dict[str, str]]], app_metadata: dict
) -> bool:
    if version_mapping.get(app_metadata['train'], {}).get(app_metadata['name']):
        return parse_version(app_metadata['version']) < parse_version(
            version_mapping[app_metadata['train']][app_metadata['name']]['version']
        )
    else:
        return False


def normalize_portal_uri(portal_uri: str, host_ip: str | None) -> str:
    if not host_ip or '0.0.0.0' not in portal_uri:
        return portal_uri

    return portal_uri.replace('0.0.0.0', host_ip)


def get_config_of_app(app_data: dict, collective_config: dict, retrieve_config: bool) -> dict:
    return {
        'config': collective_config.get(app_data['name']) or (
            get_current_app_config(app_data['name'], app_data['version']) if app_data['version'] else {}
        )
    } if retrieve_config else {}


def normalize_portal_uris(portals: dict[str, str], host_ip: str | None) -> dict[str, str]:
    return {name: normalize_portal_uri(uri, host_ip) for name, uri in portals.items()}


def list_apps(
    train_to_apps_version_mapping: dict[str, dict[str, dict[str, str]]],
    specific_app: str | None = None,
    host_ip: str | None = None,
    retrieve_config: bool = False,
) -> list[dict]:
    apps = []
    app_names = set()
    metadata = get_collective_metadata()
    collective_config = get_collective_config() if retrieve_config else {}
    # This will only give us apps which are running or in deploying state
    for app_name, app_resources in list_resources_by_project(
        project_name=f'{PROJECT_PREFIX}{specific_app}' if specific_app else None,
    ).items():
        app_name = app_name[len(PROJECT_PREFIX):]
        app_names.add(app_name)
        if app_name not in metadata:
            # The app is malformed or something is seriously wrong with it
            continue

        workloads = translate_resources_to_desired_workflow(app_resources)
        # When we stop docker service and start it again - the containers can be in exited
        # state which means we need to account for this.
        state = 'STOPPED'
        for container in workloads['container_details']:
            if container['state'] == 'starting':
                state = 'DEPLOYING'
                break
            elif container['state'] == 'running':
                state = 'RUNNING'

        app_metadata = metadata[app_name]
        app_data = {
            'name': app_name,
            'id': app_name,
            'active_workloads': get_default_workload_values() if state == 'STOPPED' else workloads,
            'state': state,
            'upgrade_available': upgrade_available_for_app(train_to_apps_version_mapping, app_metadata['metadata']),
            **app_metadata | {'portals': normalize_portal_uris(app_metadata['portals'], host_ip)}
        }
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
            app_data = {
                'name': entry.name,
                'id': entry.name,
                'active_workloads': get_default_workload_values(),
                'state': 'STOPPED',
                'upgrade_available': upgrade_available_for_app(train_to_apps_version_mapping, app_metadata['metadata']),
                **app_metadata | {'portals': normalize_portal_uris(app_metadata['portals'], host_ip)}
            }
            apps.append(app_data | get_config_of_app(app_data, collective_config, retrieve_config))

    return apps


def get_default_workload_values() -> dict:
    return {
        'containers': 0,
        'used_ports': [],
        'container_details': [],  # This would contain service name and image in use
        'volumes': [],  # This would be docker volumes
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
    workloads['containers'] = len(app_resources['containers'])
    for container in app_resources['containers']:
        service_name = container['Config']['Labels'][COMPOSE_SERVICE_KEY]
        container_ports_config = []
        for container_port, host_config in container.get('NetworkSettings', {}).get('Ports', {}).items():
            if not host_config:
                # This will happen for ports which are not exposed on the host side
                continue
            port_config = {
                'container_port': container_port.split('/')[0],
                'protocol': container_port.split('/')[1],
                'host_ports': [
                    {'host_port': host_port['HostPort'], 'host_ip': host_port['HostIp']}
                    for host_port in host_config
                ]
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
                state = 'running' if health_config['Status'] == 'healthy' else 'starting'
            else:
                state = 'running'
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

    workloads['volumes'] = [v.__dict__ for v in volumes]
    return workloads
