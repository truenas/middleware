import textwrap
import unittest.mock
import yaml
from yaml import CSafeLoader

import pytest

from middlewared.plugins.apps.upgrade import AppService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import CallError


APP_CONFIG = textwrap.dedent(
    '''
    app_version: 1.41.3.9314-a0bfb8370
    capabilities:
      - description: Plex is able to chown files.
        name: CHOWN
      - description: Plex is able to bypass permission checks for its sub-processes.
        name: FOWNER
      - description: Plex is able to bypass permission checks.
        name: DAC_OVERRIDE
      - description: Plex is able to set group ID for its sub-processes.
        name: SETGID
      - description: Plex is able to set user ID for its sub-processes.
        name: SETUID
      - description: Plex is able to kill processes.
        name: KILL
    categories:
      - media
    '''
)


@pytest.mark.parametrize('file_paths', [
    [
        '/mnt/.ix-apps/app_configs/plex/version/1.1.13/migrations/always.py',
        '/mnt/.ix-apps/app_configs/plex/version/1.1.13/migrations/only_min_version_from.py'
    ],
    [],
    [
        '/mnt/.ix-apps/app_configs/plex/version/1.1.13/migrations/always.py',
        '/mnt/.ix-apps/app_configs/plex/version/1.1.13/migrations/only_min_version_from.py',
        '/mnt/.ix-apps/app_configs/plex/version/1.1.13/migrations/only_max_versoin_from.py',
        '/mnt/.ix-apps/app_configs/plex/version/1.1.13/migrations/range_from.py'
    ]
])
@unittest.mock.patch('middlewared.plugins.apps.upgrade.subprocess.Popen')
@unittest.mock.patch('tempfile.NamedTemporaryFile')
@unittest.mock.patch('middlewared.plugins.apps.upgrade.get_current_app_config')
@unittest.mock.patch('middlewared.plugins.apps.upgrade.AppService.get_data_for_upgrade_values')
def test_upgrade_values(mock_get_data_for_upgrade_values, mock_current_config, mock_tempfile, mock_popen, file_paths):
    mock_temp_file_instance = unittest.mock.MagicMock()
    mock_temp_file_instance.name = '/mocked/tempfile/path'
    mock_tempfile.return_value.__enter__.return_value = mock_temp_file_instance
    mock_current_config.return_value = yaml.load(APP_CONFIG, Loader=CSafeLoader)

    mock_process = unittest.mock.MagicMock()
    mock_process.communicate.return_value = (APP_CONFIG.encode(), b'')
    mock_process.returncode = 0  # Mock a successful return code
    mock_popen.return_value = mock_process
    mock_get_data_for_upgrade_values.return_value = file_paths, APP_CONFIG

    middleware = Middleware()
    app_upgrade = AppService(middleware)
    app = {
        'name': 'plex',
        'metadata': {'version': '1.1.12'}
    }
    upgrade_version = {
        'version': '1.1.13'
    }

    result = app_upgrade.upgrade_values(app, upgrade_version)
    expected_dict = yaml.load(APP_CONFIG, Loader=CSafeLoader)
    assert result is not None
    assert mock_popen.call_count == len(file_paths)
    if file_paths:
        assert result == expected_dict
    else:
        assert result == APP_CONFIG


@pytest.mark.parametrize('migration_files, expected', [
    (
        {
            'error': None, 'migration_files': [
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/always.py'
                },
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/range_from.py'
                }
            ]
        },
        [
            '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/always.py',
            '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/range_from.py'
        ]
    ),
    (
        {
            'error': None, 'migration_files': [
                {
                    'error': 'Migration file is not executable',
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/always.py'
                },
                {
                    'error': 'Migration file is not executable',
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/only_min_version_from.py'
                    )
                },
                {
                    'error': 'Migration file is not executable',
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/only_max_version_from.py'
                    )
                }
            ]
        },
        CallError
    ),
    (
        {
            'error': 'Invalid Yaml', 'migration_files': []
        },
        CallError
    ),
    (
        {
            'error': 'target version should be greater than current version',
            'migration_file': []
        },
        CallError
    ),
    (
        {
            'error': 'No current or target version specified',
            'migration_file': []
        },
        CallError
    ),
    (
        {
            'error': None, 'migration_files': [
                {
                    'error': None,
                    'migration_file': '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/always.py'
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/only_min_version_from.py'
                    )
                },
                {
                    'error': None,
                    'migration_file': (
                        '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/only_max_version_from.py'
                    )
                }
            ]
        },
        [
            '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/always.py',
            '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/only_min_version_from.py',
            '/mnt/.ix-apps/app_configs/plex/versions/1.1.13/migrations/only_max_version_from.py'
        ]
    ),
])
@unittest.mock.patch('middlewared.plugins.apps.upgrade.get_migration_scripts')
@unittest.mock.patch('middlewared.plugins.apps.upgrade.get_current_app_config')
def test_get_data_for_upgrade_values(mock_current_config, mock_migration_scripts, migration_files, expected):
    middleware = Middleware()
    upgrade_app = AppService(middleware)
    mock_migration_scripts.return_value = migration_files
    mock_current_config.return_value = APP_CONFIG
    app = {
        'name': 'plex',
        'version': '1.1.12'
    }
    upgrade_version = {
        'version': '1.1.13'
    }
    if isinstance(expected, list):
        files, new_config = upgrade_app.get_data_for_upgrade_values(app, upgrade_version)
        assert files == expected
    else:
        with pytest.raises(CallError):
            upgrade_app.get_data_for_upgrade_values(app, upgrade_version)
