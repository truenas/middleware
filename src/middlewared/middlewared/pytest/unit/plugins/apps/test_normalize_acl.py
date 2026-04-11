import logging

import pytest

from middlewared.plugins.apps.schema_normalization import normalize_acl
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext


@pytest.mark.parametrize('attr, value, normalization_context', [
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
async def test_normalize_acl(attr, value, normalization_context):
    ctx = ServiceContext(Middleware(), logging.getLogger('test'))
    result = await normalize_acl(ctx, attr, value, {}, normalization_context)
    if all(value[k] for k in ('entries', 'path')):
        assert len(normalization_context['actions']) > 0
    else:
        assert len(normalization_context['actions']) == 0
    assert result == value
