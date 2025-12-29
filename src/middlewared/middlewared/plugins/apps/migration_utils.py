import os
import yaml

from apps_validation.json_schema_utils import APP_CONFIG_MIGRATIONS_SCHEMA
from jsonschema import validate, ValidationError
from pkg_resources import parse_version

from middlewared.plugins.apps.ix_apps.path import get_installed_app_version_path
from .ix_apps.utils import safe_yaml_load


def version_in_range(version: str, min_version: str = None, max_version: str = None) -> bool:
    parsed_version = parse_version(version)
    if min_version and max_version and (min_version == max_version):
        return parsed_version == parse_version(min_version)
    if min_version and parsed_version < parse_version(min_version):
        return False
    if max_version and parsed_version > parse_version(max_version):
        return False
    return True


def validate_versions(current_version: str, target_version: str):
    if not current_version or not target_version:
        return {
            'error': 'Both current and target version should be specified',
            'migration_files': []
        }
    try:
        if parse_version(current_version) >= parse_version(target_version):
            return {
                'error': 'Target version should be greater than current version',
                'migration_files': []
            }
    except ValueError:
        return {
            'error': 'Both versions should be numeric string',
            'migration_files': []
        }

    # If no error, return the default response
    return {'error': None, 'migration_files': []}


def get_migration_scripts(app_name: str, current_version: str, target_version: str) -> dict:
    migration_files = validate_versions(current_version, target_version)
    if migration_files['error']:
        return migration_files

    target_version_path = get_installed_app_version_path(app_name, target_version)
    migration_yaml_path = os.path.join(target_version_path, 'app_migrations.yaml')

    try:
        with open(migration_yaml_path, 'r') as f:
            data = safe_yaml_load(f)

        validate(data, APP_CONFIG_MIGRATIONS_SCHEMA)
    except FileNotFoundError:
        return migration_files
    except yaml.YAMLError:
        migration_files['error'] = 'Invalid YAML'
        return migration_files
    except ValidationError:
        migration_files['error'] = 'Data structure in the YAML file does not conform to the JSON schema'
        return migration_files
    else:
        for migrations in data['migrations']:
            migration_file = migrations['file']
            from_constraint = migrations.get('from', {})
            target_constraint = migrations.get('target', {})
            if (
                version_in_range(
                    current_version,
                    min_version=from_constraint.get('min_version'),
                    max_version=from_constraint.get('max_version'),
                ) and
                version_in_range(
                    target_version,
                    min_version=target_constraint.get('min_version'),
                    max_version=target_constraint.get('max_version'),
                )
            ):
                migration_file_path = os.path.join(target_version_path, f'migrations/{migration_file}')
                if os.access(migration_file_path, os.X_OK):
                    migration_files['migration_files'].append({'error': None, 'migration_file': migration_file_path})
                else:
                    migration_files['migration_files'].append({
                        'error': f'{migration_file!r} Migration file is not executable',
                        'migration_file': migration_file_path
                    })

        return migration_files
