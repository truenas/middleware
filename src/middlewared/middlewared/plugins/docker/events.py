import docker

from middlewared.plugins.apps.ix_apps.docker.utils import PROJECT_KEY, get_docker_client
from middlewared.service import ServiceContext

from .state_management import validate_state


def process_internal(context: ServiceContext, client: docker.DockerClient) -> None:
    for container_event in client.events(  # type: ignore[no-untyped-call]
            decode=True, filters={
                "type": ["container"],
                "event": [
                    "create", "destroy", "detach", "die", "health_status", "kill", "unpause",
                    "oom", "pause", "rename", "resize", "restart", "start", "stop", "update",
                ]
            }
    ):
        if not isinstance(container_event, dict):
            continue

        if project := container_event.get("Actor", {}).get("Attributes", {}).get(PROJECT_KEY):
            context.middleware.send_event("docker.events", "ADDED", id=project, fields=container_event)


def process(context: ServiceContext) -> None:
    with get_docker_client() as docker_client:
        process_internal(context, docker_client)


def setup_docker_events(context: ServiceContext) -> None:
    if not context.run_coroutine(validate_state(context, False)):
        return

    try:
        process(context)
    except Exception:
        if not context.middleware.call_sync("service.started", "docker"):
            # This is okay and can happen when docker is stopped
            return
        raise
