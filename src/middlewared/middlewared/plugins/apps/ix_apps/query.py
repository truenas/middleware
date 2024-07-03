import os
from dataclasses import dataclass

from .metadata import get_app_metadata
from .path import get_app_parent_config_path
from .docker.query import list_resources_by_project
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


def list_apps(specific_app: str | None = None) -> list[dict]:
    apps = []
    app_names = set()
    # This will only give us apps which are running or in deploying state
    for app_name, app_resources in list_resources_by_project(
        project_name=f'{PROJECT_PREFIX}{specific_app}' if specific_app else None,
    ).items():
        app_name = app_name[len(PROJECT_PREFIX):]
        app_names.add(app_name)
        if not (app_metadata := get_app_metadata(app_name)):
            # The app is malformed or something is seriously wrong with it
            continue

        workloads = translate_resources_to_desired_workflow(app_resources)
        apps.append({
            'name': app_name,
            'id': app_name,
            'active_workloads': workloads,
            'state': 'DEPLOYING' if any(
                c['state'] == 'starting' for c in workloads['container_details']
            ) else 'RUNNING',
            **app_metadata,
        })

    if specific_app and specific_app in app_names:
        return apps

    # We should now retrieve apps which are in stopped state
    with os.scandir(get_app_parent_config_path()) as scan:
        for entry in filter(
            lambda e: e.is_dir() and ((specific_app and e.name == specific_app) or e.name not in app_names), scan
        ):
            app_names.add(entry.name)
            if not (app_metadata := get_app_metadata(entry.name)):
                # The app is malformed or something is seriously wrong with it
                continue

            apps.append({
                'name': entry.name,
                'id': entry.name,
                'active_workloads': get_default_workload_values(),
                'state': 'STOPPED',
                **app_metadata,
            })

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
        })
        workloads['used_ports'].extend(container_ports_config)
        volumes.update(volume_mounts)

    workloads['volumes'] = [v.__dict__ for v in volumes]
    return workloads
