import typing

from .docker.query import list_resources_by_project
from .utils import PROJECT_PREFIX


def list_apps(specific_app: str | None = None) -> list[dict]:
    apps = []
    for app_name, app_resources in list_resources_by_project(
        project_name=f'{PROJECT_PREFIX}{specific_app}' if specific_app else None,
    ).items():
        app_name = app_name[len(PROJECT_PREFIX):]
        apps.append({
            'name': app_name,
            'id': app_name,
            'resources': app_resources,
        })
    return apps


def get_state_of_app(app_workloads: dict) -> str:
    # After discussing with Stavros, we have decided 2 status for the app:
    # 1) Running
    # 2) Stopped
    #
    # We will consider app running when it either has all containers as running or at least one container running
    # and rest of them in `exited` state. This case arises from containers we might have to set perms etc.
    #
    # We will consider app as stopped when all containers are in `exited` state.
    # TODO: Add deploying state as well
    state = 'STOPPED'
    # TODO: Complete me
    return state
