import collections
import unittest

import pytest

from middlewared.plugins.apps.ix_apps.query import list_apps


AVAILABLE_MAPPING = {
    'community': {
        'whoogle': {
            'version': '1.0.20',
            'app_version': '0.9.0'
        },
        'rsyncd': {
            'version': '1.0.14',
            'app_version': '1.0.0'
        },
        'actual-budget': {
            'version': '1.1.13',
            'app_version': '24.10.1'
        },
    }
}
KWARGS = {
    'host_ip': None,
    'retrieve_config': False,
    'image_update_cache': {
        'registry-1.docker.io/actualbudget/actual-server:24.10.1': False,
        'registry-1.docker.io/library/bash:latest': False
    }
}
METADATA = {
    'actual-budget': {
        'custom_app': False,
        'human_version': '24.10.1_1.1.13',
        'metadata': {
            'app_version': '24.10.1',
            'capabilities': [],
            'categories': ['media'],
            'description': 'Actual Budget is a super fast and privacy-focused app for managing your finances.',
            'home': 'https://actualbudget.org',
            'host_mounts': [],
            'last_update': '2024-10-23 14:29:45',
            'lib_version': '1.1.4',
            'lib_version_hash': '6e32ff5969906d9c3a10fea2b17fdd3197afb052d3432344da03188d8a907113',
            'name': 'actual-budget',
            'title': 'Actual Budget',
            'train': 'community',
            'version': '1.1.13'
        },
        'migrated': False,
        'portals': {
            'Web UI': 'http://0.0.0.0:31012/'
        },
        'version': '1.1.13'
    }
}


def common_impl(
    mock_get_collective_metadata, mock_list_resources_by_project,
    mock_translate_resources_to_desired_workflow, mock_upgrade_available_for_app,
    scandir, workload, desired_state
):
    mock_get_collective_metadata.return_value = METADATA
    mock_list_resources_by_project.return_value = collections.defaultdict(None, workload)
    mock_translate_resources_to_desired_workflow.return_value = workload['ix-actual-budget']
    mock_upgrade_available_for_app.return_value = (False, '1.21.0', '1.0.0')
    mock_entry1 = unittest.mock.Mock(is_file=lambda: True, name='config1.json')
    scandir.return_value.__enter__.return_value = [mock_entry1]

    result = list_apps(AVAILABLE_MAPPING, **KWARGS)
    assert result is not None
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]['state'] == desired_state


@pytest.mark.parametrize(
    'workload',
    [
        {
            'ix-actual-budget': {
                'containers': 2,
                'container_details': [
                    {
                        'service_name': 'actual_budget',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'starting',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'db',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                ],
                'images': [
                    'actualbudget/actual-server:24.10.1',
                    'bash'
                ]
            }
        },
        {
            'ix-actual-budget': {
                'containers': 2,
                'container_details': [
                    {
                        'service_name': 'actual_budget',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'created',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'db',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                ],
                'images': [
                    'actualbudget/actual-server:24.10.1',
                    'bash'
                ]
            }
        },
        {
            'ix-actual-budget': {
                'containers': 4,
                'container_details': [
                    {
                        'service_name': 'actual_budget',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'running',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'redis',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'db',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'web',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                ],
                'images': [
                    'actualbudget/actual-server:24.10.1',
                    'bash'
                ]
            }
        },
        {
            'ix-actual-budget': {
                'containers': 4,
                'container_details': [
                    {
                        'service_name': 'actual_budget',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'running',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'redis',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'db',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'web',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'running',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                ],
                'images': [
                    'actualbudget/actual-server:24.10.1',
                    'bash'
                ]
            }
        },
        {
            'ix-actual-budget': {
                'containers': 4,
                'container_details': [
                    {
                        'service_name': 'actual_budget',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'exited',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'redis',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'running',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'db',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'web',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'running',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                ],
                'images': [
                    'actualbudget/actual-server:24.10.1',
                    'bash'
                ]
            }
        },
        {
            'ix-actual-budget': {
                'containers': 4,
                'container_details': [
                    {
                        'service_name': 'actual_budget',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'redis',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'db',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'crashed',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                    {
                        'service_name': 'web',
                        'image': 'actualbudget/actual-server:24.10.1',
                        'state': 'running',
                        'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                    },
                ],
                'images': [
                    'actualbudget/actual-server:24.10.1',
                    'bash'
                ]
            }
        },
    ],
    ids=[
        'starting-crashed', 'created-crashed', 'running-crashedx3', 'running-crashedx2-running',
        'exited-running-crashed-running', 'crashedx3-running'
    ]
)
@unittest.mock.patch('os.scandir')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
def test_app_event_crashed(
    mock_get_collective_metadata, mock_list_resources_by_project,
    mock_translate_resources_to_desired_workflow, mock_upgrade_available_for_app,
    scandir, workload
):
    common_impl(
        mock_get_collective_metadata, mock_list_resources_by_project, mock_translate_resources_to_desired_workflow,
        mock_upgrade_available_for_app, scandir, workload, 'CRASHED',
    )


@pytest.mark.parametrize('workload', [
    {
        'ix-actual-budget': {
            'containers': 2,
            'container_details': [
                {
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'starting',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
                {
                    'service_name': 'db',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'created',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
            ],
            'images': [
                'actualbudget/actual-server:24.10.1',
                'bash'
            ]
        }
    },
    {
        'ix-actual-budget': {
            'containers': 2,
            'container_details': [
                {
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'running',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
                {
                    'service_name': 'db',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'starting',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
            ],
            'images': [
                'actualbudget/actual-server:24.10.1',
                'bash'
            ]
        }
    },
    {
        'ix-actual-budget': {
            'containers': 2,
            'container_details': [
                {
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'exited',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
                {
                    'service_name': 'db',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'starting',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
            ],
            'images': [
                'actualbudget/actual-server:24.10.1',
                'bash'
            ]
        }
    },
    {
        'ix-actual-budget': {
            'containers': 2,
            'container_details': [
                {
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'created',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
                {
                    'service_name': 'db',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'created',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
            ],
            'images': [
                'actualbudget/actual-server:24.10.1',
                'bash'
            ]
        }
    },
], ids=['starting-created', 'running-starting', 'exited-starting', 'created-created'])
@unittest.mock.patch('os.scandir')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
def test_app_event_deploying(
    mock_get_collective_metadata, mock_list_resources_by_project,
    mock_translate_resources_to_desired_workflow, mock_upgrade_available_for_app,
    scandir, workload
):
    common_impl(
        mock_get_collective_metadata, mock_list_resources_by_project, mock_translate_resources_to_desired_workflow,
        mock_upgrade_available_for_app, scandir, workload, 'DEPLOYING',
    )


@pytest.mark.parametrize('workload', [
    {
        'ix-actual-budget': {
            'containers': 2,
            'container_details': [
                {
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'running',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
                {
                    'service_name': 'db',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'running',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
            ],
            'images': [
                'actualbudget/actual-server:24.10.1',
                'bash'
            ]
        }
    },
], ids=['running-running'])
@unittest.mock.patch('os.scandir')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
def test_app_event_running(
    mock_get_collective_metadata, mock_list_resources_by_project,
    mock_translate_resources_to_desired_workflow, mock_upgrade_available_for_app,
    scandir, workload
):
    common_impl(
        mock_get_collective_metadata, mock_list_resources_by_project, mock_translate_resources_to_desired_workflow,
        mock_upgrade_available_for_app, scandir, workload, 'RUNNING',
    )


@pytest.mark.parametrize('workload', [
    {
        'ix-actual-budget': {
            'containers': 2,
            'container_details': [
                {
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'exited',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
                {
                    'service_name': 'db',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'exited',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
            ],
            'images': [
                'actualbudget/actual-server:24.10.1',
                'bash'
            ]
        }
    },
    {
        'ix-actual-budget': {
            'containers': 2,
            'container_details': [
                {
                    'service_name': 'actual_budget',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'stopping',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
                {
                    'service_name': 'db',
                    'image': 'actualbudget/actual-server:24.10.1',
                    'state': 'stopping',
                    'id': 'a30866299d667597baca8433aa51d83948075f4ae7e99d88569d6ec0bfcf89f0'
                },
            ],
            'images': [
                'actualbudget/actual-server:24.10.1',
                'bash'
            ]
        }
    },
], ids=['exited-exited', 'stopping-stopping'])
@unittest.mock.patch('os.scandir')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.upgrade_available_for_app')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.translate_resources_to_desired_workflow')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.list_resources_by_project')
@unittest.mock.patch('middlewared.plugins.apps.ix_apps.query.get_collective_metadata')
def test_app_event_stopped(
    mock_get_collective_metadata, mock_list_resources_by_project,
    mock_translate_resources_to_desired_workflow, mock_upgrade_available_for_app,
    scandir, workload
):
    common_impl(
        mock_get_collective_metadata, mock_list_resources_by_project, mock_translate_resources_to_desired_workflow,
        mock_upgrade_available_for_app, scandir, workload, 'STOPPED',
    )
