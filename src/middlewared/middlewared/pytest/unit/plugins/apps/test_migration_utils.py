import textwrap
import unittest.mock

import pytest

from jsonschema import validate, ValidationError
from packaging.version import Version

from middlewared.plugins.apps.migration_utils import (
    APP_CONFIG_MIGRATIONS_SCHEMA, get_migration_scripts, validate_versions, version_in_range,
)


MOCKED_YAML = textwrap.dedent(
    '''
    migrations:
      # No constraints - always run
      - file: always.py
        # Should run for any current/target combination

      # Only min_version "from"
      - file: only_min_version_from.py
        from:
          min_version: 1.0.0

      # Only max_version "from"
      - file: only_max_version_from.py
        from:
          max_version: 1.9.9

      # min_version and max_version "from"
      - file: range_from.py
        from:
          min_version: 1.0.0
          max_version: 1.9.9

      # Only min_version "target"
      - file: only_min_version_target.py
        target:
          min_version: 2.0.0

      # Only max_version "target"
      - file: only_max_version_target.py
        target:
          max_version: 1.9.9

      # min_version and max_version "target"
      - file: range_target.py
        target:
          min_version: 2.0.0
          max_version: 2.9.9

      # Complex: from range and target range
      - file: range_to_range.py
        from:
          min_version: 1.0.0
          max_version: 1.9.9
        target:
          min_version: 2.0.0
          max_version: 2.9.9

      # Exact version match (using min_version/max_version)
      - file: exact_version.py
        from:
          min_version: 1.0.0
          max_version: 1.0.0
    '''
)


@pytest.mark.parametrize('app_name, current_version, target_version, expected', [
    (
        'plex', '1.0.0', '2.0.0',
        {
            'error': None, 'migration_files': [
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/always.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_min_version_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_max_version_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_from.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_min_version_target.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_target.py'
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_to_range.py'
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/exact_version.py'
                },
            ]
        }
    ),
    (
        'plex', '1.5.0', '2.1.0',
        {
            'error': None, 'migration_files': [
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/always.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_min_version_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_max_versoin_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_from.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_min_version_target.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_target.py'
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_to_range.py'
                },
            ]
        }
    ),
    (
        'plex', '0.9.9', None,
        {
            'error': 'Both current and target version should be specified',
            'migration_files': []
        }
    ),
    (
        'plex', '1.5.0', None,
        {
            'error': 'Both current and target version should be specified',
            'migration_files': []
        }
    ),
    (
        'plex', '0.9.9', '2.0.0',
        {
            'error': None, 'migration_files': [
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/always.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_max_versoin_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_min_version_target.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_target.py'
                }
            ]
        }
    ),
    (
        'plex', '1.5.0', '1.9.9',
        {
            'error': None, 'migration_files': [
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/always.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_min_versoin_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_max_versoin_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/range_from.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/2.0.0/migrations/only_max_version_target.py'
                    )
                }
            ]
        }
    ),
    (
        'plex', None, None,
        {
            'error': 'Both current and target version should be specified', 'migration_files': []
        }
    ),
    (
        'plex', '2.0.0', '1.5.0',
        {
            'error': 'Target version should be greater than current version', 'migration_files': []
        }
    )
])
@unittest.mock.patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=MOCKED_YAML)
@unittest.mock.patch('os.path.join')
@unittest.mock.patch('os.access')
def test_get_migration_scripts(mock_access, mock_join, mock_open, app_name, current_version, target_version, expected):
    migration_file_paths = [item['migration_file'] for item in expected['migration_files']]
    mock_join.side_effect = [
        '/mnt/.ix-apps/app_configs',
        '/mnt/.ix-apps/app_configs/plex',
        '/mnt/.ix-apps/app_configs/plex/versions',
        f'/mnt/.ix-apps/app_configs/plex/versions/{target_version}',
        '/path/to/migration.yaml',
        *migration_file_paths,
    ]
    mock_access.return_value = True
    result = get_migration_scripts(app_name, current_version, target_version)
    assert result == expected


@pytest.mark.parametrize('current_version, target_version, expected', [
    (
        '1.0.0', '1.5.0',
        {
            'error': None, 'migration_files': []
        }
    ),
    (
        '1.5.0', '2.0.0',
        {
            'error': None, 'migration_files': []
        }
    ),
    (
        '2.0.0', '1.5.0',
        {
            'error': 'Target version should be greater than current version',
            'migration_files': []
        }
    ),
    (
        None, '1.5.0',
        {
            'error': 'Both current and target version should be specified',
            'migration_files': []
        }
    ),
    (
        None, None,
        {
            'error': 'Both current and target version should be specified',
            'migration_files': []
        }
    ),
    (
        'None', '1.1.1',
        {
            'error': 'Both versions should be numeric string',
            'migration_files': []
        }
    ),
    (
        '', '1.0.0',
        {
            'error': 'Both current and target version should be specified',
            'migration_files': []
        }
    )

])
def test_validate_versions(current_version, target_version, expected):
    result = validate_versions(current_version, target_version)
    assert result == expected


@pytest.mark.parametrize('version, expected', [
    ('1.0.0', '1.0.0'),
    ('1.1.13', '1.1.13'),
    ('abc', ValueError),
    ('', ValueError)
])
def test_parse_versions(version, expected):
    if isinstance(expected, str):
        assert Version(version) == Version(expected)
    else:
        with pytest.raises(ValueError):
            Version(version)


@pytest.mark.parametrize('version, min_version, max_version, expected', [
    (
        '1.0.0', '1.0.0', '1.5.0', True
    ),
    (
        '0.9.9', '1.0.0', '2.0.0', False
    ),
    (
        '1.8.0', '1.5.0', '2.0.0', True
    ),
    (
        '2.2.0', '1.0.0', '2.1.0', False
    ),
    (
        '1.0.0', '1.0.0', '1.0.0', True
    ),
    (
        '1.0.0', None, '2.0.0', True
    ),
    (
        '1.0.0', 'None', '2.1.0', ValueError
    ),
    (
        'Invalid', '1.0.0', '2.0.0', ValueError
    )
])
def test_version_in_range(version, min_version, max_version, expected):
    if isinstance(expected, bool):
        result = version_in_range(version, min_version, max_version)
        assert result == expected
    else:
        with pytest.raises(ValueError):
            version_in_range(version, min_version, max_version)


@pytest.mark.parametrize('valid_yaml_data', [
    {
        'migrations': [
            {
                'file': 'always.py',
                'from': {'min_version': '1.0.0', 'max_version': '1.9.9'}
            }
        ]
    },
    {
        'migrations': [
            {
                'file': 'always.py',
                'target': {'min_version': '1.0.0', 'max_version': '1.9.9'}
            }
        ]
    },
    {
        'migrations': [
            {
                'file': 'always.py'
            }
        ]
    },
    {
        'migrations': [
            {
                'file': 'always.py',
                'from': {'min_version': '1.0.0', 'max_version': '1.9.9'},
                'target': {'min_version': '2.0.0', 'max_version': '2.5.0'}
            }
        ]
    }
])
def test_validate_yaml_schema_valid(valid_yaml_data):
    assert validate(valid_yaml_data, APP_CONFIG_MIGRATIONS_SCHEMA) is None


@pytest.mark.parametrize('invalid_yaml_data', [
    {'invalid_key': 'invalid_value'},
    {},
    None
])
def test_validate_yaml_schema_invalid_structure(invalid_yaml_data):
    with pytest.raises(ValidationError):
        validate(invalid_yaml_data, APP_CONFIG_MIGRATIONS_SCHEMA)
