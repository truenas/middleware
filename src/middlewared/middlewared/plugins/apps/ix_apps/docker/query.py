from collections import defaultdict
from itertools import chain, repeat
from typing import Any

import docker.errors

from .utils import PROJECT_KEY, get_docker_client


def list_resources_by_project(project_name: str | None = None) -> dict[str, dict[str, list[Any]]]:
    retries = 2
    while retries > 0:
        try:
            return list_resources_by_project_internal(project_name)
        except docker.errors.NotFound:
            retries -= 1
            if retries == 0:
                raise

    raise ValueError(f"Could not list resources for project {project_name}")


def list_resources_by_project_internal(project_name: str | None = None) -> dict[str, dict[str, list[Any]]]:
    with get_docker_client() as client:
        label_filter = {"label": f"{PROJECT_KEY}={project_name}" if project_name else PROJECT_KEY}
        containers = client.containers.list(all=True, filters=label_filter, sparse=False)
        networks = client.networks.list(filters=label_filter)
        volumes = client.volumes.list(filters=label_filter)
        projects: defaultdict[str, dict[str, list[Any]]] = defaultdict(
            lambda: {"containers": [], "networks": [], "volumes": []}
        )

        for resource_type, resource in chain(
            zip(repeat("containers"), containers), zip(repeat("networks"), networks), zip(repeat("volumes"), volumes)
        ):
            projects[
                resource.labels[PROJECT_KEY] if resource_type == "containers" else resource.attrs["Labels"][PROJECT_KEY]
            ][resource_type].append(resource.attrs)

    return projects
