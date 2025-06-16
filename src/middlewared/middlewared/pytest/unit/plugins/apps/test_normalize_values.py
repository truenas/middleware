import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('dict_attrs, values, update, context, expected', [
    (
        # Empty questions list - just reserved names
        [],
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
        # Empty questions list - just reserved names (update mode)
        [],
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
async def test_normalize_values(dict_attrs, values, update, context, expected):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    result = await app_schema_obj.normalize_values(
        dict_attrs,
        values,
        update,
        context
    )
    assert result == expected
