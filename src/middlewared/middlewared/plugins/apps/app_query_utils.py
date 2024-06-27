import os

from .app_utils import get_app_metadata
from .app_path_utils import get_app_parent_config_path
from .docker.query import list_resources_by_project
from .utils import PROJECT_PREFIX


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

        apps.append({
            'name': app_name,
            'id': app_name,
            'resources': app_resources,
            'state': 'RUNNING',
            **app_metadata,
        })

    # We should now retrieve apps which are in stopped state
    with os.scandir(get_app_parent_config_path()) as scan:
        for entry in filter(lambda e: e.is_dir() and e.name not in app_names, scan):
            app_names.add(entry.name)
            if not (app_metadata := get_app_metadata(entry.name)):
                # The app is malformed or something is seriously wrong with it
                continue

            apps.append({
                'name': entry.name,
                'id': entry.name,
                'resources': {},
                'state': 'STOPPED',
                **app_metadata,
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
