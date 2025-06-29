import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('attr, value, context', [
    (
        {'schema': {'type': 'dict'}},
        {
            'entries': [{'type': 'ALLOW', 'permissions': 'read'}],
            'path': '/mnt/data'
        },
        {'actions': []},
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'entries': [{'type': 'ALLOW', 'permissions': 'write'}],
            'path': '/mnt/data'
        },
        {
            'actions': [
                {
                    'method': 'apply_acls',
                    'args': [
                        {
                            'path': {
                                'entries': [
                                    {
                                        'type': 'ALLOW',
                                        'permissions': 'read'
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        },
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'entries': [],
            'path': ''
        },
        {'actions': []},
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'entries': [{'type': 'ALLOW', 'permissions': 'rw'}],
            'path': ''
        },
        {'actions': []},
    ),
])
@pytest.mark.asyncio
async def test_normalize_acl(attr, value, context):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    result = await app_schema_obj.normalize_acl(attr, value, '', context)
    if all(value[k] for k in ('entries', 'path')):
        assert len(context['actions']) > 0
    else:
        assert len(context['actions']) == 0
    assert result == value
