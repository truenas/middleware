import itertools
import typing

from middlewared.service_exception import CallError

from .app_lifecycle_utils import get_rendered_templates_of_app
from .utils import PROJECT_PREFIX, run


def compose_action(
    app_name: str, app_version: str, action: typing.Literal['up', 'down'], *,
    force_recreate: bool = False, remove_orphans: bool = False,
):
    compose_files = list(itertools.chain(
        *[('-f', item) for item in get_rendered_templates_of_app(app_name, app_version)]
    ))
    if not compose_files:
        raise CallError(f'No compose files found for app {app_name!r}')

    args = ['-p', f'{PROJECT_PREFIX}{app_name}', action]

    if action == 'up':
        args.append('-d')
        if force_recreate:
            args.append('--force-recreate')
        if remove_orphans:
            args.append('--remove-orphans')
    elif action == 'down':
        if remove_orphans:
            args.append('--remove-orphans')
        args.append('-v')
    else:
        raise CallError(f'Invalid action {action!r} for app {app_name!r}')

    cp = run(['docker-compose'] + compose_files + args)
    if cp.returncode != 0:
        raise CallError(f'Failed {action!r} action for {app_name!r} app: {cp.stderr}')
