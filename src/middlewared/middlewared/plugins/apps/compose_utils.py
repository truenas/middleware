import itertools
import typing

from middlewared.service_exception import CallError

from .ix_apps.lifecycle import get_rendered_templates_of_app
from .utils import PROJECT_PREFIX, run


def compose_action(
    app_name: str, app_version: str, action: typing.Literal['up', 'down'], *,
    force_recreate: bool = False, remove_orphans: bool = False, remove_images: bool = False,
    remove_volumes=False,
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
        if remove_images:
            args.extend(['--rmi', 'all'])
        if remove_volumes:
            args.append('-v')
    else:
        raise CallError(f'Invalid action {action!r} for app {app_name!r}')

    # TODO: We will likely have a configurable timeout on this end
    cp = run(['docker', 'compose'] + compose_files + args, timeout=1200)
    if cp.returncode != 0:
        raise CallError(f'Failed {action!r} action for {app_name!r} app: {cp.stderr}')
