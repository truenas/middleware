import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.schema import Dict


@pytest.mark.parametrize('app_detail, values, expected', [
    (
        {
            'healthy': True,
            'supported': True,
            'healthy_error': None,
            'location': '/mnt/.ix-apps/truenas_catalog/trains/community/actual-budget/1.1.11',
            'last_update': '2024-10-13 21:17:53',
            'required_features': [],
            'human_version': '24.10.1_1.1.11',
            'version': '1.1.11',
            'app_metadata': {
                'app_version': '24.10.1',
                'capabilities': [],
                'categories': ['media'],
                'description': 'Actual Budget is a super fast and privacy-focused app for managing your finances.',
                'home': 'https://actualbudget.org',
                'host_mounts': [],
                'lib_version': '1.1.2',
                'lib_version_hash': '3bf14311f7547731c94dbd4059f7aca95272210409631acbc5603a06223921e4',
                'name': 'actual-budget',
                'run_as_context': [],
                'sources': [],
                'title': 'Actual Budget',
                'train': 'community',
                'version': '1.1.11'
            },
            'schema': {
                'groups': [
                    {
                        'name': 'Actual Budget Configuration',
                        'description': 'Configure Actual Budget'
                    }
                ],
                'questions': [
                    {
                        'variable': 'actual_budget',
                        'label': '',
                        'group': 'Actual Budget Configuration',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'additional_envs',
                                    'label': 'Additional Environment Variables',
                                    'description': 'Configure additional environment variables for Actual Budget.',
                                    'schema': {
                                        'type': 'list',
                                        'default': [],
                                        'items': []
                                    }
                                }
                            ]
                        }
                    }
                ],
                'readme': '',
                'changelog': None,
                'values': {
                    'actual_budget': {
                        'additional_envs': []
                    },
                    'run_as': {
                        'user': 568,
                        'group': 568
                    },
                    'network': {
                        'web_port': 31012,
                        'host_network': False
                    },
                    'storage': {
                        'data': {
                            'type': 'ix_volume',
                            'ix_volume_config': {
                                'acl_enable': False,
                                'dataset_name': 'data'
                            }
                        },
                        'additional_storage': []
                    },
                    'resources': {
                        'limits': {
                            'cpus': 2,
                            'memory': 4096
                        }
                    }
                }
            }
        },
        {},
        {
            'ix_certificates': {},
            'ix_certificate_authorities': {},
            'ix_volumes': {},
            'ix_context': {}
        }
    )
])
@pytest.mark.asyncio
async def test_normalize_and_validate(app_detail, values, expected):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    # Mock validate_values to return an empty dict (or the input values)
    # since normalize_values expects a mutable dictionary
    middleware['app.schema.validate_values'] = lambda item_details, values, update, app_data: values or {}
    new_values = await app_schema_obj.normalize_and_validate_values(
        item_details=app_detail,
        values=values,
        update=False,
        app_dir='/path/to/app'
    )
    assert new_values == expected
