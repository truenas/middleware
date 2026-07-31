import os
import typing

import yaml

from middlewared.utils.io import write_if_changed
from middlewared.utils.yaml import safe_yaml_load

from .path import get_collective_config_path, get_collective_metadata_path, get_installed_app_metadata_path
from .portals import get_portals_and_app_notes
from .utils import AppErrorReason, dump_yaml

# Keys we cannot render an app without. Anything outside this set is defaulted instead of being
# treated as fatal (portals -> {}, notes -> None, migrated -> False), so metadata written by an
# older release is never misreported as broken - a false ERROR would block a working app.
APP_METADATA_REQUIRED_KEYS: frozenset[str] = frozenset(('metadata', 'custom_app', 'version', 'human_version'))
# Keys of the nested catalog metadata that upgrade detection indexes
APP_CATALOG_METADATA_REQUIRED_KEYS: frozenset[str] = frozenset(('name', 'train', 'version'))


def _load_app_yaml(yaml_path: str) -> dict[str, typing.Any]:
    """ wrapper around safe_yaml_load that ensures a dict is always returned """
    try:
        with open(yaml_path, 'r') as f:
            return safe_yaml_load(f, dict)
    except (OSError, yaml.YAMLError, ValueError):
        # OSError covers a missing file as well as one we cannot read at all, i.e. EACCES/EIO/EISDIR
        return {}


def get_app_metadata(app_name: str) -> dict[str, typing.Any]:
    return _load_app_yaml(get_installed_app_metadata_path(app_name))


def app_metadata_error(app_metadata: dict[str, typing.Any]) -> AppErrorReason | None:
    """
    Report why ``app_metadata`` cannot be used, if it cannot. Performs no I/O.
    """
    if not app_metadata:
        return 'METADATA_MISSING'

    if not APP_METADATA_REQUIRED_KEYS.issubset(app_metadata):
        return 'METADATA_INCOMPLETE'

    catalog_metadata = app_metadata['metadata']
    if not isinstance(catalog_metadata, dict) or not APP_CATALOG_METADATA_REQUIRED_KEYS.issubset(catalog_metadata):
        return 'METADATA_INCOMPLETE'

    return None


def get_app_metadata_checked(app_name: str) -> tuple[dict[str, typing.Any], AppErrorReason | None]:
    """
    Like ``get_app_metadata`` but reports why the app's metadata is unusable, if it is.
    """
    try:
        with open(get_installed_app_metadata_path(app_name), 'r') as f:
            app_metadata: dict[str, typing.Any] = safe_yaml_load(f, dict)
    except FileNotFoundError:
        return {}, 'METADATA_MISSING'
    except (OSError, yaml.YAMLError, ValueError):
        # We cannot read it at all (EACCES/EIO/EISDIR), it is not valid YAML, or it is not a mapping
        return {}, 'METADATA_UNREADABLE'

    return app_metadata, app_metadata_error(app_metadata)


def resolve_app_metadata(
    app_name: str, collective_metadata: dict[str, typing.Any], has_resources: bool, installing: set[str],
) -> tuple[dict[str, typing.Any], AppErrorReason | None, bool]:
    """
    Resolve one app's metadata along with the reason it is unusable, if any.

    The returned boolean is ``False`` when the app should be ignored entirely. Costs no I/O for
    apps present in ``collective_metadata``, which is every app on a healthy system.
    """
    if (app_metadata := collective_metadata.get(app_name)) is not None:
        return app_metadata, app_metadata_error(app_metadata), True

    app_metadata, error_reason = get_app_metadata_checked(app_name)
    if error_reason is None:
        # The app's own metadata is intact, it just has not made it into the collective metadata
        # yet (or no longer is, mid-delete). Ignoring it here also means a collective metadata file
        # that is itself missing or corrupt cannot flip every app on the system into ERROR.
        return app_metadata, None, False

    if error_reason == 'METADATA_MISSING' and not has_resources and app_name in installing:
        # The app directory is created a moment before its metadata is written, so an install in
        # flight is indistinguishable from an abandoned directory by looking at the filesystem alone
        return app_metadata, None, False

    return app_metadata, error_reason, True


def update_app_metadata(
    app_name: str, app_version_details: dict[str, typing.Any], migrated: bool | None = None,
    custom_app: bool = False,
) -> None:
    migrated = get_app_metadata(app_name).get('migrated', False) if migrated is None else migrated
    write_if_changed(get_installed_app_metadata_path(app_name), dump_yaml({
            'metadata': app_version_details['app_metadata'],
            'migrated': migrated,
            'custom_app': custom_app,
            **{k: app_version_details[k] for k in ('version', 'human_version')},
            **get_portals_and_app_notes(app_name, app_version_details['version']),
            # TODO: We should not try to get portals for custom apps for now
        }), perms=0o600, raise_error=False)


def update_app_metadata_for_portals(app_name: str, version: str) -> None:
    # This should be called after config of app has been updated as that will render compose files
    app_metadata = get_app_metadata(app_name)

    # Using write_if_changed ensures atomicity of the write via writing to a temporary
    # file then renaming over existing one.
    write_if_changed(get_installed_app_metadata_path(app_name), dump_yaml({
        **app_metadata,
        **get_portals_and_app_notes(app_name, version),
    }), perms=0o600, raise_error=False)


def get_collective_config() -> dict[str, typing.Any]:
    return _load_app_yaml(get_collective_config_path())


def get_collective_metadata() -> dict[str, typing.Any]:
    return _load_app_yaml(get_collective_metadata_path())


def update_app_yaml_for_last_update(version_path: str, last_update: str) -> None:
    app_yaml_path = os.path.join(version_path, 'app.yaml')

    app_config = _load_app_yaml(app_yaml_path)
    app_config['last_update'] = last_update

    write_if_changed(app_yaml_path, dump_yaml(app_config), perms=0o600, raise_error=False)
