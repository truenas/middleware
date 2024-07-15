import copy
import pathlib
import typing
import yaml

from middlewared.service_exception import CallError

from .path import (
    get_installed_app_config_path, get_installed_app_rendered_dir_path, get_installed_app_version_path,
)
from .utils import CONTEXT_KEY_NAME, run


def get_rendered_templates_of_app(app_name: str, version: str) -> list[str]:
    result = []
    for entry in pathlib.Path(get_installed_app_rendered_dir_path(app_name, version)).iterdir():
        if entry.is_file() and entry.name.endswith('.yaml'):
            result.append(entry.as_posix())
    return result


def write_new_app_config(app_name: str, version: str, values: dict[str, typing.Any]) -> None:
    with open(get_installed_app_config_path(app_name, version), 'w') as f:
        f.write(yaml.safe_dump(values))


def get_current_app_config(app_name: str, version: str) -> dict:
    with open(get_installed_app_config_path(app_name, version), 'r') as f:
        return yaml.safe_load(f)


def render_compose_templates(app_version_path: str, values_file_path: str):
    cp = run(['/usr/bin/apps_render_app', 'render', '--path', app_version_path, '--values', values_file_path])
    if cp.returncode != 0:
        # FIXME: We probably want to log app related issues to it's own logging file so as to not spam middleware
        raise CallError(f'Failed to render compose templates: {cp.stderr}')


def update_app_config(app_name: str, version: str, values: dict[str, typing.Any]) -> None:
    write_new_app_config(app_name, version, values)
    render_compose_templates(
        get_installed_app_version_path(app_name, version), get_installed_app_config_path(app_name, version)
    )


def get_action_context(app_name: str) -> dict[str, typing.Any]:
    # TODO: See what needs to be added/removed here
    return copy.deepcopy({
        'operation': None,
        'is_install': False,
        'is_rollback': False,
        'is_update': False,
        'is_upgrade': False,
        'upgrade_metadata': {},
        'app_name': app_name,
    })


def add_context_to_values(
    app_name: str, values: dict[str, typing.Any], *, install: bool = False, update: bool = False, upgrade: bool = False,
    upgrade_metadata: dict[str, typing.Any] = None, rollback: bool = False,
) -> dict[str, typing.Any]:
    assert install or update or upgrade or rollback, 'At least one of install, update, rollback or upgrade must be True'
    assert sum([install, rollback, update, upgrade]) <= 1, 'Only one of install, update, or upgrade can be True.'
    if upgrade:
        assert upgrade_metadata is not None, 'upgrade_metadata must be specified if upgrade is True.'

    action_context = get_action_context(app_name)

    operation_map = {
        'INSTALL': install,
        'ROLLBACK': rollback,
        'UPDATE': update,
        'UPGRADE': upgrade,
    }

    for operation, _ in filter(lambda i: i[1], operation_map.items()):
        action_context.update({
            'operation': operation,
            f'is_{operation.lower()}': True,
            **({'upgrade_metadata': upgrade_metadata} if operation == 'UPGRADE' else {})
        })

    values[CONTEXT_KEY_NAME] = action_context

    return values
