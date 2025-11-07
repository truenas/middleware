import itertools
import logging
import subprocess
import tempfile
import typing

from middlewared.service_exception import CallError

from .ix_apps.lifecycle import get_rendered_templates_of_app
from .utils import PROJECT_PREFIX, run


logger = logging.getLogger('app_lifecycle')


def compose_action(
    app_name: str, app_version: str, action: typing.Literal['up', 'down', 'pull'], *,
    force_recreate: bool = False, remove_orphans: bool = False, remove_images: bool = False,
    remove_volumes: bool = False, pull_images: bool = False,
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
            # This needs to happen because --force-recreate doesn't recreate docker networks
            # So for example, an app was running and then system has been rebooted - the docker network
            # remains there but the relevant interfaces it created do not and if the app didn't had a restart
            # policy of always, when attempting to start the app again - it will fail because the network
            # is not recreated with compose up action and we need an explicit down
            compose_action(app_name, app_version, 'down', remove_orphans=True)
        if remove_orphans:
            args.append('--remove-orphans')
        if pull_images:
            args.append('--pull=always')
    elif action == 'down':
        if remove_orphans:
            args.append('--remove-orphans')
        if remove_images:
            args.extend(['--rmi', 'all'])
        if remove_volumes:
            args.append('-v')
    elif action == 'pull':
        args.extend(['--policy', 'always'])
    else:
        raise CallError(f'Invalid action {action!r} for app {app_name!r}')

    # TODO: We will likely have a configurable timeout on this end
    cp = run(['docker', '--config', '/etc/docker', 'compose'] + compose_files + args, timeout=1200)
    if cp.returncode != 0:
        logger.error('Failed %r action for %r app: %s', action, app_name, cp.stderr)
        err_msg = f'Failed {action!r} action for {app_name!r} app.'
        if 'toomanyrequests:' in cp.stderr:
            err_msg += ' It appears you have reached your pull rate limit. Please try again later.'
        err_msg += ' Please check /var/log/app_lifecycle.log for more details'
        raise CallError(err_msg)


def validate_compose_config(compose_yaml: str) -> tuple[bool, str]:
    """
    Validate a Docker Compose YAML configuration.

    Args:
        compose_yaml: YAML string containing the compose configuration

    Returns:
        A tuple of (is_valid, error_message). If valid, error_message is empty string.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=True) as tmp_file:
        tmp_file.write(compose_yaml)
        tmp_file.flush()

        cp = run(
            ['docker', '--config', '/etc/docker', 'compose', '-f', tmp_file.name, 'config'],
            stdout=subprocess.DEVNULL,
            timeout=30
        )

        if cp.returncode != 0:
            error_msg = cp.stderr.strip() if cp.stderr else 'Invalid compose configuration'
            return False, error_msg

        return True, ''


def collect_logs(app_name: str, app_version: str) -> str:
    compose_files = list(itertools.chain(
        *[('-f', item) for item in get_rendered_templates_of_app(app_name, app_version)]
    ))
    if not compose_files:
        return f'No compose files found for app {app_name!r}'

    args = ['-p', f'{PROJECT_PREFIX}{app_name}', 'logs', '--no-color', '--timestamps']

    cp = run(
        ['docker', '--config', '/etc/docker', 'compose'] + compose_files + args,
        timeout=60, check=False, stderr=subprocess.STDOUT,
    )
    if cp.returncode != 0:
        logger.error('Failed to collect logs for %r app: %s', app_name, cp.stdout)
        return ''

    return cp.stdout
