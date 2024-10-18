import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.schema import Dict


@pytest.mark.parametrize('dict_obj, values, update, context, expected', [
    (
        Dict(
            'actual-budget',
            Dict('run_as'),
            Dict('network'),
            Dict('resources')
        ),
        {
            'ix_certificates': {},
            'ix_certificate_authorities': {},
            'ix_volumes': {},
            'ix_context': {}
        },
        False,
        {'app': {'name': 'app', 'path': '/path/to/app'}, 'actions': []},
        (
            {
                'ix_certificates': {},
                'ix_certificate_authorities': {},
                'ix_volumes': {},
                'ix_context': {}
            },
            {
                'app': {
                    'name': 'app',
                    'path': '/path/to/app'
                },
                'actions': []
            }
        )
    ),
    (
        Dict(
            'actual-budget',
            Dict('run_as'),
            Dict('network'),
            Dict('resources')
        ),
        {
            'ix_certificates': {},
            'ix_certificate_authorities': {},
            'ix_volumes': {},
            'ix_context': {}
        },
        True,
        {'app': {'name': 'app', 'path': '/path/to/app'}, 'actions': []},
        (
            {
                'ix_certificates': {},
                'ix_certificate_authorities': {},
                'ix_volumes': {},
                'ix_context': {}
            },
            {
                'app': {
                    'name': 'app',
                    'path': '/path/to/app'
                },
                'actions': []
            }
        )
    ),
])
@pytest.mark.asyncio
async def test_normalize_values(dict_obj, values, update, context, expected):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    result = await app_schema_obj.normalize_values(
        dict_obj,
        values,
        update,
        context
    )
    assert result == expected
