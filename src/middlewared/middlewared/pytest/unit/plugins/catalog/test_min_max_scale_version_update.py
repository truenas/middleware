import pytest

from middlewared.plugins.catalog.apps_util import minimum_scale_version_check_update


@pytest.mark.parametrize('version_data, expected', [
    (
        {
            'healthy': True,
            'supported': True,
            'healthy_error': None,
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.11',
            'last_update': '2024-10-09 20:30:25',
            'human_version': '24.10.1_1.1.11',
            'chart_metadata': {
                'annotations': {
                    'min_scale_version': '21.01',
                    'max_scale_version': '24.04'
                }
            },
            'version': '1.1.11',
            'schema': {
                'groups': [
                    {
                        'name': 'Actual Budget Configuration',
                        'description': 'Configure Actual Budget'
                    }
                ]
            }
        },
        {
            'healthy': True,
            'supported': False,
            'healthy_error': None,
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.11',
            'last_update': '2024-10-09 20:30:25',
            'human_version': '24.10.1_1.1.11',
            'chart_metadata': {
                'annotations': {
                    'min_scale_version': '21.01',
                    'max_scale_version': '24.04'
                }
            },
            'version': '1.1.11',
            'schema': {
                'groups': [
                    {
                        'name': 'Actual Budget Configuration',
                        'description': 'Configure Actual Budget'
                    }
                ]
            }
        }
    ),
    (
        {
            'healthy': True,
            'supported': True,
            'healthy_error': None,
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.11',
            'last_update': '2024-10-09 20:30:25',
            'human_version': '24.10.1_1.1.11',
            'chart_metadata': {
                'annotations': {
                    'min_scale_version': '21.01',
                    'max_scale_version': '27.04'
                }
            },
            'version': '1.1.11',
            'schema': {
                'groups': [
                    {
                        'name': 'Actual Budget Configuration',
                        'description': 'Configure Actual Budget'
                    }
                ]
            }
        },
        {
            'healthy': True,
            'supported': True,
            'healthy_error': None,
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.11',
            'last_update': '2024-10-09 20:30:25',
            'human_version': '24.10.1_1.1.11',
            'chart_metadata': {
                'annotations': {
                    'min_scale_version': '21.01',
                    'max_scale_version': '27.04'
                }
            },
            'version': '1.1.11',
            'schema': {
                'groups': [
                    {
                        'name': 'Actual Budget Configuration',
                        'description': 'Configure Actual Budget'
                    }
                ]
            }
        }
    ),
    (
        {
            'healthy': True,
            'supported': True,
            'healthy_error': None,
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.11',
            'last_update': '2024-10-09 20:30:25',
            'human_version': '24.10.1_1.1.11',
            'chart_metadata': {
                'annotations': {
                    'min_scale_version': '26.04',
                    'max_scale_version': '24.04'
                }
            },
            'version': '1.1.11',
            'schema': {
                'groups': [
                    {
                        'name': 'Actual Budget Configuration',
                        'description': 'Configure Actual Budget'
                    }
                ]
            }
        },
        {
            'healthy': True,
            'supported': False,
            'healthy_error': None,
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.11',
            'last_update': '2024-10-09 20:30:25',
            'human_version': '24.10.1_1.1.11',
            'chart_metadata': {
                'annotations': {
                    'min_scale_version': '26.04',
                    'max_scale_version': '24.04'
                }
            },
            'version': '1.1.11',
            'schema': {
                'groups': [
                    {
                        'name': 'Actual Budget Configuration',
                        'description': 'Configure Actual Budget'
                    }
                ]
            }
        }
    ),
])
def test_min_max_scale_version_update(mocker, version_data, expected):
    mocker.patch('middlewared.plugins.catalog.apps_util.sw_info', return_value={'version': '25.04.0'})
    result = minimum_scale_version_check_update(version_data)
    assert result == expected
