import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('attr, value, complete_config, context', [
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [{'type': 'ALLOW', 'permissions': 'write'}],
                'path': '/mnt/data'
            }
        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {'actions': [], 'app': {'name': 'test_app'}}
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [],
                'path': ''
            }
        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {'actions': [], 'app': {'name': 'test_app'}}
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [],
                'path': ''
            }

        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {
            'actions': [
                {
                    'method': 'update_volumes',
                    'args': [[
                        {
                            'name': 'volume_1'
                        }
                    ]]
                }
            ],
            'app': {'name': 'test_app'}
        }
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [],
                'path': ''
            }

        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {
            'actions': [
                {
                    'method': 'update_volumes',
                    'args': [[
                        {
                            'name': 'volume_2'
                        }
                    ]]
                }
            ],
            'app': {'name': 'test_app'}
        }
    ),
])
@pytest.mark.asyncio
async def test_normalize_ix_volumes(attr, value, complete_config, context):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    result = await app_schema_obj.normalize_ix_volume(attr, value, complete_config, context)
    assert len(context['actions']) > 0
    assert value['dataset_name'] in [v['name'] for v in context['actions'][0]['args'][-1]]
    assert result == value
