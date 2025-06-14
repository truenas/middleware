import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService, REF_MAPPING
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('attr_schema, ref, value, update', [
    (
        {
            'variable': 'cert_id',
            'schema': {
                'type': 'int',
                '$ref': ['definitions/certificate']
            }
        },
        'definitions/certificate',
        1234,
        False
    ),
    (
        {
            'variable': 'acl_config',
            'schema': {
                'type': 'dict',
                '$ref': ['normalize/acl'],
                'attrs': []
            }
        },
        'normalize/acl',
        {'entries': [], 'path': '/mnt/data'},
        False
    ),
    (
        {
            'variable': 'acl_config',
            'schema': {
                'type': 'dict',
                '$ref': ['normalize/acl'],
                'attrs': []
            }
        },
        'normalize/acl',
        {'entries': [], 'path': '/mnt/data'},
        True
    ),
    (
        {
            'variable': 'cert_id',
            'schema': {
                'type': 'int',
                'null': True,
                '$ref': ['definitions/certificate']
            }
        },
        'definitions/certificate',
        None,
        False
    )
])
@pytest.mark.asyncio
async def test_normalize_question(attr_schema, ref, value, update):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    middleware[f'app.schema.normalize_{REF_MAPPING[ref]}'] = lambda *args: value
    result = await app_schema_obj.normalize_question(attr_schema, value, update, {}, {})
    assert result == value


@pytest.mark.parametrize('attr_schema, ref, value, update', [
    (
        {
            'variable': 'cert_list',
            'schema': {
                'type': 'list',
                '$ref': ['definitions/certificate'],
                'items': [
                    {
                        'variable': 'cert_item',
                        'schema': {
                            'type': 'int',
                            '$ref': ['definitions/certificate']
                        }
                    }
                ]
            }
        },
        'definitions/certificate',
        [1, 2, 3],
        False
    ),
])
@pytest.mark.asyncio
async def test_normalize_question_List(attr_schema, ref, value, update):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    # Mock the normalize functions to return the value as-is
    middleware[f'app.schema.normalize_{REF_MAPPING[ref]}'] = lambda *args: args[1]  # Return the value parameter

    result = await app_schema_obj.normalize_question(attr_schema, value, update, {}, {})
    assert result == value


@pytest.mark.parametrize('attr_schema, value, update', [
    (
        {
            'variable': 'storage_config',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'volume',
                        'schema': {
                            'type': 'dict',
                            '$ref': ['normalize/ix_volume']
                        }
                    },
                    {
                        'variable': 'certificate',
                        'schema': {
                            'type': 'int',
                            '$ref': ['definitions/certificate']
                        }
                    }
                ]
            }
        },
        {
            'volume': {'dataset_name': 'mydata', 'properties': {}},
            'certificate': 123
        },
        False
    ),
])
@pytest.mark.asyncio
async def test_normalize_nested_dict_with_refs(attr_schema, value, update):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)

    # Mock the normalize functions
    async def mock_normalize_ix_volume(attr, val, config, context):
        # Simulate adding volume to config
        config['ix_volumes'][val['dataset_name']] = {'path': f'/mnt/ix-apps/{val["dataset_name"]}'}
        return val

    async def mock_normalize_certificate(attr, val, config, context):
        # Simulate adding certificate to config
        config['ix_certificates'][val] = {'name': f'cert-{val}'}
        return val

    middleware['app.schema.normalize_ix_volume'] = mock_normalize_ix_volume
    middleware['app.schema.normalize_certificate'] = mock_normalize_certificate

    complete_config = {
        'ix_volumes': {},
        'ix_certificates': {}
    }
    context = {'actions': []}

    result = await app_schema_obj.normalize_question(attr_schema, value, update, complete_config, context)

    # Check that the normalization was applied
    assert result == value
    assert 'mydata' in complete_config['ix_volumes']
    assert 123 in complete_config['ix_certificates']
