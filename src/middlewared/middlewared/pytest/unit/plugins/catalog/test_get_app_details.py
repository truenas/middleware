import pytest

from middlewared.plugins.catalog.apps_util import get_app_details


@pytest.mark.parametrize('app_data, versions, expected', [
    (
        {
            'app_readme': '',
            'categories': [
                'media'
            ],
            'description': '',
            'healthy': True,
            'healthy_error': None,
            'home': 'https://actualbudget.org',
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget',
            'latest_version': '1.1.11',
            'latest_app_version': '24.10.1',
            'latest_human_version': '24.10.1_1.1.11',
            'last_update': '12-02-21 00:00:00',
            'name': 'actual-budget',
            'recommended': False,
            'title': 'Actual Budget',
        },
        {
            '1.0.1': {
                'name': 'chia',
                'categories': [],
                'app_readme': None,
                'location': '/mnt/mypool/ix-applications/catalogs/'
                            'github_com_truenas_charts_git_master/charts/chia',
                'healthy': True,
                'supported': True,
                'healthy_error': None,
                'required_features': [],
                'version': '1.0.1',
                'human_version': '1.15.12',
                'home': None,
                'readme': None,
                'changelog': None,
                'last_update': '1200-20-00 00:00:00',
                'app_metadata': {
                    'name': 'chia',
                    'train': 'stable',
                    'version': '1.0.1',
                    'app_version': '1.0.1',
                    'title': 'chia',
                    'description': 'desc',
                    'home': 'None',
                },
                'schema': {
                    "groups": [],
                    "questions": []
                }
            }
        },
        {
            'app_readme': '',
            'categories': ['media'],
            'description': '',
            'healthy': True,
            'healthy_error': None,
            'home': 'https://actualbudget.org',
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget',
            'latest_version': '1.1.11',
            'latest_app_version': '24.10.1',
            'latest_human_version': '24.10.1_1.1.11',
            'last_update': '12-02-21 00:00:00',
            'name': 'actual-budget',
            'recommended': False,
            'title': 'Actual Budget',
            'versions': {
                '1.0.1': {
                    'name': 'chia',
                    'categories': [],
                    'app_readme': None,
                    'location': '/path/to/app/1.0.1',
                    'healthy': True,
                    'supported': True,
                    'healthy_error': None,
                    'required_features': [],
                    'version': '1.0.1',
                    'human_version': '1.15.12',
                    'home': None,
                    'readme': None,
                    'changelog': None,
                    'last_update': '1200-20-00 00:00:00',
                    'app_metadata': {
                        'name': 'chia',
                        'train': 'stable',
                        'version': '1.0.1',
                        'app_version': '1.0.1',
                        'title': 'chia',
                        'description': 'desc',
                        'home': 'None',
                    },
                    'schema': {
                        'groups': [],
                        'questions': []
                    },
                    'values': {}
                }
            }
        }
    ),
    (
        {
            'app_readme': '',
            'categories': [
                'media'
            ],
            'description': '',
            'healthy': True,
            'healthy_error': None,
            'home': 'https://actualbudget.org',
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget',
            'latest_version': '1.1.11',
            'latest_app_version': '24.10.1',
            'latest_human_version': '24.10.1_1.1.11',
            'last_update': '12-02-21 00:00:00',
            'name': 'actual-budget',
            'recommended': False,
            'title': 'Actual Budget',
        },
        {},
        {
            'app_readme': '',
            'categories': ['media'],
            'description': '',
            'healthy': True,
            'healthy_error': None,
            'home': 'https://actualbudget.org',
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget',
            'latest_version': '1.1.11',
            'latest_app_version': '24.10.1',
            'latest_human_version': '24.10.1_1.1.11',
            'last_update': '12-02-21 00:00:00',
            'name': 'actual-budget',
            'recommended': False,
            'title': 'Actual Budget',
            'versions': {}
        }
    ),
])
def test_get_app_details(mocker, app_data, versions, expected):
    mocker.patch('middlewared.plugins.catalog.apps_util.normalize_questions')
    mocker.patch('middlewared.plugins.catalog.apps_util.retrieve_cached_versions_data', return_value=versions)
    if isinstance(expected, dict):
        result = get_app_details('/path/to/app', app_data, {})
        assert expected == result
