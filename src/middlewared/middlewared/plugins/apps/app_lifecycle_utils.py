import copy
import pathlib
import typing

from .app_path_utils import get_installed_app_rendered_dir_path
from .schema_utils import CONTEXT_KEY_NAME


def get_rendered_templates_of_app(app_name: str, version: str) -> list[str]:
    result = []
    for entry in pathlib.Path(get_installed_app_rendered_dir_path(app_name, version)).iterdir():
        if entry.is_file() and entry.name.endswith('.yaml'):
            result.append(entry.name)
    return result


def get_action_context(app_name: str) -> dict[str, typing.Any]:
    # TODO: See what needs to be added/removed here
    return copy.deepcopy({
        'operation': None,
        'is_install': False,
        'is_update': False,
        'is_upgrade': False,
        'upgrade_metadata': {},
        'app_name': app_name,
    })


def add_context_to_values(
    app_name: str, values: dict[str, typing.Any], *, install: bool = False, update: bool = False, upgrade: bool = False,
    upgrade_metadata: dict[str, typing.Any] = None,
) -> dict[str, typing.Any]:
    assert install or update or upgrade, 'At least one of install, update, or upgrade must be True.'
    assert sum([install, update, upgrade]) <= 1, 'Only one of install, update, or upgrade can be True.'
    if upgrade:
        assert upgrade_metadata is not None, 'upgrade_metadata must be specified if upgrade is True.'

    action_context = get_action_context(app_name)

    operation_map = {
        'INSTALL': install,
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
