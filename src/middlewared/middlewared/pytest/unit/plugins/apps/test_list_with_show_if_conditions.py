"""
Comprehensive tests for list items with show_if conditions.

These tests verify that list items with conditional fields (show_if) properly
evaluate conditions based on actual item values and handle discriminator fields.
Note: Immutability in lists is no longer supported and related tests have been disabled.
"""
from unittest.mock import patch

from middlewared.plugins.apps.schema_construction_utils import (
    generate_pydantic_model, NOT_PROVIDED, construct_schema
)


# Helper functions for schemas
def _get_minio_schema():
    """Get basic MinIO schema structure."""
    return [{
        'variable': 'storage',
        'schema': {
            'type': 'dict',
            'attrs': [{
                'variable': 'data_dirs',
                'schema': {
                    'type': 'list',
                    'default': [{
                        'type': 'ix_volume',
                        'mount_path': '/data1',
                        'ix_volume_config': {'dataset_name': 'data1'}
                    }],
                    'items': [{
                        'variable': 'item',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'type',
                                    'schema': {
                                        'type': 'string',
                                        'required': True,
                                        'default': 'host_path'
                                    }
                                },
                                {
                                    'variable': 'mount_path',
                                    'schema': {
                                        'type': 'path',
                                        'required': True
                                    }
                                },
                                {
                                    'variable': 'host_path_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['type', '=', 'host_path']],
                                        'attrs': [{
                                            'variable': 'path',
                                            'schema': {
                                                'type': 'string',  # Changed from hostpath to string for testing
                                                'required': True
                                            }
                                        }]
                                    }
                                },
                                {
                                    'variable': 'ix_volume_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['type', '=', 'ix_volume']],
                                        'attrs': [{
                                            'variable': 'dataset_name',
                                            'schema': {
                                                'type': 'string',
                                                'required': True
                                            }
                                        }]
                                    }
                                }
                            ]
                        }
                    }]
                }
            }]
        }
    }]


def _get_minio_schema_with_enum():
    """Get MinIO schema with proper enum for discriminator field."""
    schema = _get_minio_schema()
    # Add enum to type field for proper discrimination
    type_field = schema[0]['schema']['attrs'][0]['schema']['items'][0]['schema']['attrs'][0]
    type_field['schema']['enum'] = [
        {'value': 'host_path', 'description': 'Host Path'},
        {'value': 'ix_volume', 'description': 'ix Volume'}
    ]
    return schema


# MinIO Enterprise Tests
@patch('middlewared.plugins.apps.pydantic_utils.os.path.isfile', return_value=True)
@patch('middlewared.plugins.apps.pydantic_utils.os.path.isdir', return_value=True)
def test_minio_with_defaults(mock_isdir, mock_isfile):
    """Test MinIO schema using default values."""
    schema = _get_minio_schema()

    # Using defaults (type='ix_volume' in default)
    model = generate_pydantic_model(schema, 'TestMinioDefaults', NOT_PROVIDED, NOT_PROVIDED)
    instance = model()

    # Verify defaults are applied correctly
    assert instance.storage.data_dirs[0]['type'] == 'ix_volume'
    assert instance.storage.data_dirs[0]['ix_volume_config']['dataset_name'] == 'data1'
    assert 'host_path_config' not in instance.storage.data_dirs[0] or \
           instance.storage.data_dirs[0].get('host_path_config') is None


@patch('middlewared.plugins.apps.pydantic_utils.os.path.isfile', return_value=True)
@patch('middlewared.plugins.apps.pydantic_utils.os.path.isdir', return_value=True)
def test_minio_explicit_ix_volume(mock_isdir, mock_isfile):
    """Test MinIO schema with explicit ix_volume type."""
    schema = _get_minio_schema()
    values = {
        'storage': {
            'data_dirs': [
                {
                    'type': 'ix_volume',
                    'mount_path': '/data1',
                    'ix_volume_config': {
                        'dataset_name': 'data1'
                    }
                }
            ]
        }
    }

    model = generate_pydantic_model(schema, 'TestMinioIxVolume', values, NOT_PROVIDED)
    instance = model(**values)

    assert instance.storage.data_dirs[0]['type'] == 'ix_volume'
    assert instance.storage.data_dirs[0]['ix_volume_config']['dataset_name'] == 'data1'


@patch('middlewared.plugins.apps.pydantic_utils.os.path.isfile', return_value=True)
@patch('middlewared.plugins.apps.pydantic_utils.os.path.isdir', return_value=True)
def test_minio_explicit_host_path(mock_isdir, mock_isfile):
    """Test MinIO schema with explicit host_path type."""
    schema = _get_minio_schema()
    values = {
        'storage': {
            'data_dirs': [
                {
                    'type': 'host_path',
                    'mount_path': '/data1',
                    'host_path_config': {
                        'path': '/mnt/data'
                    }
                }
            ]
        }
    }

    model = generate_pydantic_model(schema, 'TestMinioHostPath', values, NOT_PROVIDED)
    instance = model(**values)

    assert instance.storage.data_dirs[0]['type'] == 'host_path'
    assert instance.storage.data_dirs[0]['host_path_config']['path'] == '/mnt/data'


@patch('middlewared.plugins.apps.pydantic_utils.os.path.isfile', return_value=True)
@patch('middlewared.plugins.apps.pydantic_utils.os.path.isdir', return_value=True)
def test_minio_mixed_storage_types(mock_isdir, mock_isfile):
    """Test MinIO with mixed storage types in the same list."""
    schema = _get_minio_schema_with_enum()
    values = {
        'storage': {
            'data_dirs': [
                {
                    'type': 'host_path',
                    'mount_path': '/data1',
                    'host_path_config': {'path': '/mnt/data1'}
                },
                {
                    'type': 'ix_volume',
                    'mount_path': '/data2',
                    'ix_volume_config': {'dataset_name': 'data2'}
                },
                {
                    'type': 'host_path',
                    'mount_path': '/data3',
                    'host_path_config': {'path': '/mnt/data3'}
                }
            ]
        }
    }

    model = generate_pydantic_model(schema, 'TestMinioMixed', values, NOT_PROVIDED)
    instance = model(**values)

    assert instance.storage.data_dirs[0]['type'] == 'host_path'
    assert instance.storage.data_dirs[1]['type'] == 'ix_volume'
    assert instance.storage.data_dirs[2]['type'] == 'host_path'


# Nested Show If Tests
def test_nested_show_if_basic():
    """Test basic nested show_if conditions."""
    schema = [{
        'variable': 'rules',
        'schema': {
            'type': 'list',
            'items': [{
                'variable': 'rule',
                'schema': {
                    'type': 'dict',
                    'attrs': [
                        {
                            'variable': 'type',
                            'schema': {
                                'type': 'string',
                                'required': True,
                                'enum': [
                                    {'value': 'filter'},
                                    {'value': 'other'}
                                ]
                            }
                        },
                        {
                            'variable': 'advanced',
                            'schema': {
                                'type': 'boolean',
                                'default': False
                            }
                        },
                        {
                            'variable': 'filter_config',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'filter']],
                                'attrs': [
                                    {
                                        'variable': 'pattern',
                                        'schema': {
                                            'type': 'string',
                                            'required': True
                                        }
                                    },
                                    {
                                        'variable': 'regex_options',
                                        'schema': {
                                            'type': 'dict',
                                            'show_if': [['advanced', '=', True]],
                                            'attrs': [{
                                                'variable': 'case_sensitive',
                                                'schema': {
                                                    'type': 'boolean',
                                                    'default': True
                                                }
                                            }]
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }]
        }
    }]

    # Test with nested show_if conditions
    values = {
        'rules': [
            {
                'type': 'filter',
                'advanced': True,
                'filter_config': {
                    'pattern': '*.txt',
                    'regex_options': {
                        'case_sensitive': False
                    }
                }
            },
            {
                'type': 'filter',
                'advanced': False,
                'filter_config': {
                    'pattern': '*.log'
                }
            },
            {
                'type': 'other'
            }
        ]
    }

    model = generate_pydantic_model(schema, 'TestNested', values, NOT_PROVIDED)
    instance = model(**values)

    assert instance.rules[0]['filter_config']['pattern'] == '*.txt'
    assert instance.rules[0]['filter_config']['regex_options']['case_sensitive'] is False
    assert instance.rules[1]['filter_config']['pattern'] == '*.log'
    assert instance.rules[2]['type'] == 'other'


def test_complex_nested_show_if():
    """Test complex nested show_if with multiple conditions."""
    schema = {
        'schema': {
            'questions': [{
                'variable': 'services',
                'schema': {
                    'type': 'list',
                    'items': [{
                        'variable': 'service',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'enabled',
                                    'schema': {'type': 'boolean', 'default': False}
                                },
                                {
                                    'variable': 'mode',
                                    'schema': {
                                        'type': 'string',
                                        'default': 'basic',
                                        'enum': [
                                            {'value': 'basic'},
                                            {'value': 'advanced'}
                                        ]
                                    }
                                },
                                {
                                    'variable': 'advanced_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['enabled', '=', True], ['mode', '=', 'advanced']],
                                        'attrs': [
                                            {
                                                'variable': 'level',
                                                'schema': {'type': 'int', 'default': 1}
                                            },
                                            {
                                                'variable': 'expert_settings',
                                                'schema': {
                                                    'type': 'dict',
                                                    'show_if': [['level', '>', 5]],
                                                    'attrs': [{
                                                        'variable': 'param',
                                                        'schema': {'type': 'string', 'required': True}
                                                    }]
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }]
                }
            }]
        }
    }

    # Test various combinations
    values = {
        'services': [
            {
                'enabled': True,
                'mode': 'advanced',
                'advanced_config': {
                    'level': 7,
                    'expert_settings': {'param': 'expert_value'}
                }
            }
        ]
    }

    result = construct_schema(schema, values, False)
    assert not result['verrors'], f"Should work with expert settings: {result['verrors']}"


# Default Values Tests
def test_defaults_vs_explicit():
    """Test that defaults work correctly with show_if in lists."""
    schema = [{
        'variable': 'config',
        'schema': {
            'type': 'dict',
            'attrs': [{
                'variable': 'items',
                'schema': {
                    'type': 'list',
                    'default': [
                        {'mode': 'auto', 'auto_config': {'interval': 60}}
                    ],
                    'items': [{
                        'variable': 'item',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'mode',
                                    'schema': {
                                        'type': 'string',
                                        'required': True,
                                        'default': 'manual',
                                        'enum': [
                                            {'value': 'auto'},
                                            {'value': 'manual'}
                                        ]
                                    }
                                },
                                {
                                    'variable': 'manual_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['mode', '=', 'manual']],
                                        'attrs': [{
                                            'variable': 'value',
                                            'schema': {
                                                'type': 'string',
                                                'required': True
                                            }
                                        }]
                                    }
                                },
                                {
                                    'variable': 'auto_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['mode', '=', 'auto']],
                                        'attrs': [{
                                            'variable': 'interval',
                                            'schema': {
                                                'type': 'int',
                                                'required': True
                                            }
                                        }]
                                    }
                                }
                            ]
                        }
                    }]
                }
            }]
        }
    }]

    # Test 1: Use defaults
    model_defaults = generate_pydantic_model(schema, 'TestDefaults', {}, NOT_PROVIDED)
    m1 = model_defaults()
    assert m1.config.items[0]['mode'] == 'auto'
    assert m1.config.items[0]['auto_config']['interval'] == 60

    # Test 2: Override with explicit values
    explicit_values = {
        'config': {
            'items': [
                {'mode': 'manual', 'manual_config': {'value': 'test'}}
            ]
        }
    }
    model_explicit = generate_pydantic_model(schema, 'TestExplicit', explicit_values, NOT_PROVIDED)
    m2 = model_explicit(**explicit_values)
    assert m2.config.items[0]['mode'] == 'manual'
    assert m2.config.items[0]['manual_config']['value'] == 'test'


def test_empty_list_handling():
    """Test that empty lists work correctly with show_if schemas."""
    schema = [{
        'variable': 'items',
        'schema': {
            'type': 'list',
            'items': [{
                'variable': 'item',
                'schema': {
                    'type': 'dict',
                    'attrs': [
                        {
                            'variable': 'type',
                            'schema': {
                                'type': 'string',
                                'required': True
                            }
                        },
                        {
                            'variable': 'config',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'special']],
                                'attrs': [{
                                    'variable': 'value',
                                    'schema': {
                                        'type': 'string',
                                        'required': True
                                    }
                                }]
                            }
                        }
                    ]
                }
            }]
        }
    }]

    # Empty list should be valid
    model = generate_pydantic_model(schema, 'TestEmpty', {'items': []}, NOT_PROVIDED)
    instance = model(items=[])
    assert instance.items == []


# Construct Schema Tests
def test_construct_schema_with_list_show_if():
    """Test construct_schema with list items having show_if conditions."""
    schema = {
        'schema': {
            'questions': [{
                'variable': 'resources',
                'schema': {
                    'type': 'list',
                    'items': [{
                        'variable': 'resource',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'type',
                                    'schema': {
                                        'type': 'string',
                                        'required': True,
                                        'enum': [
                                            {'value': 'cpu'},
                                            {'value': 'memory'}
                                        ]
                                    }
                                },
                                {
                                    'variable': 'cpu_limit',
                                    'schema': {
                                        'type': 'int',
                                        'show_if': [['type', '=', 'cpu']],
                                        'required': True
                                    }
                                },
                                {
                                    'variable': 'memory_limit',
                                    'schema': {
                                        'type': 'string',
                                        'show_if': [['type', '=', 'memory']],
                                        'required': True
                                    }
                                }
                            ]
                        }
                    }]
                }
            }]
        }
    }

    # Test with proper values
    values = {
        'resources': [
            {'type': 'cpu', 'cpu_limit': 4},
            {'type': 'memory', 'memory_limit': '8Gi'}
        ]
    }

    result = construct_schema(schema, values, False)
    assert not result['verrors']
    assert result['new_values']['resources'][0]['cpu_limit'] == 4
    assert result['new_values']['resources'][1]['memory_limit'] == '8Gi'


def test_construct_schema_with_comparison_operators():
    """Test show_if with comparison operators in list items."""
    schema = {
        'schema': {
            'questions': [{
                'variable': 'configs',
                'schema': {
                    'type': 'list',
                    'items': [{
                        'variable': 'config',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'priority',
                                    'schema': {
                                        'type': 'int',
                                        'default': 1
                                    }
                                },
                                {
                                    'variable': 'urgent_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['priority', '>', 5]],
                                        'attrs': [{
                                            'variable': 'alert',
                                            'schema': {
                                                'type': 'boolean',
                                                'default': True
                                            }
                                        }]
                                    }
                                },
                                {
                                    'variable': 'low_priority_note',
                                    'schema': {
                                        'type': 'string',
                                        'show_if': [['priority', '<=', 2]],
                                        'default': 'Low priority item'
                                    }
                                }
                            ]
                        }
                    }]
                }
            }]
        }
    }

    values = {
        'configs': [
            {'priority': 7, 'urgent_config': {'alert': True}},
            {'priority': 1, 'low_priority_note': 'Can wait'}
        ]
    }

    result = construct_schema(schema, values, False)
    assert not result['verrors']
    assert result['new_values']['configs'][0]['priority'] == 7
    assert result['new_values']['configs'][1]['low_priority_note'] == 'Can wait'


# Multiple Discriminator Tests
def test_multiple_discriminator_fields():
    """Test that multiple discriminator fields fall back to standard approach."""
    schema = [{
        'variable': 'items',
        'schema': {
            'type': 'list',
            'items': [{
                'variable': 'item',
                'schema': {
                    'type': 'dict',
                    'attrs': [
                        {
                            'variable': 'type',
                            'schema': {
                                'type': 'string',
                                'required': True
                            }
                        },
                        {
                            'variable': 'enabled',
                            'schema': {
                                'type': 'boolean',
                                'default': False
                            }
                        },
                        {
                            'variable': 'type_config',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'special']],
                                'attrs': [{
                                    'variable': 'value',
                                    'schema': {'type': 'string', 'required': True}
                                }]
                            }
                        },
                        {
                            'variable': 'enabled_config',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['enabled', '=', True]],
                                'attrs': [{
                                    'variable': 'setting',
                                    'schema': {'type': 'string', 'required': True}
                                }]
                            }
                        }
                    ]
                }
            }]
        }
    }]

    # Multiple fields (type and enabled) are referenced in show_if
    # Should use standard approach, not discriminator optimization
    values = {
        'items': [
            {
                'type': 'special',
                'enabled': True,
                'type_config': {'value': 'test'},
                'enabled_config': {'setting': 'on'}
            }
        ]
    }

    model = generate_pydantic_model(schema, 'TestMultiple', values, NOT_PROVIDED)
    instance = model(**values)

    assert instance.items[0]['type'] == 'special'
    assert instance.items[0]['enabled'] is True


# Constraint Tests
def test_min_max_constraints_with_show_if():
    """Test that min/max constraints work with show_if conditions."""
    schema = {
        'schema': {
            'questions': [{
                'variable': 'limits',
                'schema': {
                    'type': 'list',
                    'min': 1,
                    'max': 3,
                    'items': [{
                        'variable': 'limit',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'type',
                                    'schema': {
                                        'type': 'string',
                                        'required': True,
                                        'enum': [
                                            {'value': 'cpu'},
                                            {'value': 'memory'}
                                        ]
                                    }
                                },
                                {
                                    'variable': 'cpu_cores',
                                    'schema': {
                                        'type': 'int',
                                        'show_if': [['type', '=', 'cpu']],
                                        'min': 1,
                                        'max': 16,
                                        'required': True
                                    }
                                },
                                {
                                    'variable': 'memory_gb',
                                    'schema': {
                                        'type': 'int',
                                        'show_if': [['type', '=', 'memory']],
                                        'min': 1,
                                        'max': 64,
                                        'required': True
                                    }
                                }
                            ]
                        }
                    }]
                }
            }]
        }
    }

    # Valid: within min/max range
    valid_values = {
        'limits': [
            {'type': 'cpu', 'cpu_cores': 4},
            {'type': 'memory', 'memory_gb': 8}
        ]
    }
    result = construct_schema(schema, valid_values, False)
    assert not result['verrors']

    # Invalid: too many items
    invalid_values = {
        'limits': [
            {'type': 'cpu', 'cpu_cores': 4},
            {'type': 'memory', 'memory_gb': 8},
            {'type': 'cpu', 'cpu_cores': 2},
            {'type': 'memory', 'memory_gb': 16}
        ]
    }
    result = construct_schema(schema, invalid_values, False)
    assert result['verrors']
    assert any('limits' in str(e) for e in result['verrors'])


# ============================================================================
# COMPREHENSIVE TESTS FOR SONARR-LIKE STORAGE BUG
# ============================================================================

@patch('middlewared.plugins.apps.pydantic_utils.os.path.isfile', return_value=True)
@patch('middlewared.plugins.apps.pydantic_utils.os.path.isdir', return_value=True)
def test_sonarr_storage_host_path_with_acl_enabled(mock_isdir, mock_isfile):
    """Test the exact Sonarr storage scenario with host_path and ACL enabled.

    This reproduces the bug where path is required even when acl_enable=True
    and the path field has show_if: [['acl_enable', '=', False]].
    """
    schema = {
        'schema': {
            'questions': [{
                'variable': 'storage',
                'schema': {
                    'type': 'dict',
                    'attrs': [{
                        'variable': 'additional_storage',
                        'schema': {
                            'type': 'list',
                            'default': [],
                            'items': [{
                                'variable': 'storageEntry',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'type',
                                            'schema': {
                                                'type': 'string',
                                                'required': True,
                                                'default': 'ix_volume',
                                                'enum': [
                                                    {'value': 'host_path'},
                                                    {'value': 'ix_volume'}
                                                ]
                                            }
                                        },
                                        {
                                            'variable': 'mount_path',
                                            'schema': {
                                                'type': 'path',
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'host_path_config',
                                            'schema': {
                                                'type': 'dict',
                                                'show_if': [['type', '=', 'host_path']],
                                                'attrs': [
                                                    {
                                                        'variable': 'acl_enable',
                                                        'schema': {
                                                            'type': 'boolean',
                                                            'default': False
                                                        }
                                                    },
                                                    {
                                                        'variable': 'path',
                                                        'schema': {
                                                            'type': 'string',
                                                            'show_if': [['acl_enable', '=', False]],
                                                            'required': True
                                                        }
                                                    },
                                                    {
                                                        'variable': 'acl',
                                                        'schema': {
                                                            'type': 'dict',
                                                            'show_if': [['acl_enable', '=', True]],
                                                            'attrs': [
                                                                {
                                                                    'variable': 'path',
                                                                    'schema': {
                                                                        'type': 'string',
                                                                        'required': True
                                                                    }
                                                                }
                                                            ]
                                                        }
                                                    }
                                                ]
                                            }
                                        },
                                        {
                                            'variable': 'ix_volume_config',
                                            'schema': {
                                                'type': 'dict',
                                                'show_if': [['type', '=', 'ix_volume']],
                                                'attrs': [
                                                    {
                                                        'variable': 'dataset_name',
                                                        'schema': {
                                                            'type': 'string',
                                                            'required': True,
                                                            'default': 'storage'
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                }
                            }]
                        }
                    }]
                }
            }]
        }
    }

    # Test 1: host_path with acl_enable=True (path should NOT be required)
    values = {
        'storage': {
            'additional_storage': [{
                'type': 'host_path',
                'mount_path': '/test',
                'host_path_config': {
                    'acl_enable': True,
                    'acl': {
                        'path': '/mnt/data'
                    }
                }
            }]
        }
    }

    result = construct_schema(schema, values, False)
    assert len(result['verrors'].errors) == 0, \
        f"Path should NOT be required when acl_enable=True, but got: {result['verrors'].errors}"

    # Test 2: host_path with acl_enable=False (path should be required)
    values2 = {
        'storage': {
            'additional_storage': [{
                'type': 'host_path',
                'mount_path': '/test',
                'host_path_config': {
                    'acl_enable': False
                    # Missing path - should fail
                }
            }]
        }
    }

    result2 = construct_schema(schema, values2, False)
    assert len(result2['verrors'].errors) > 0, "Should fail when acl_enable=False and no path"


def test_discriminator_with_nested_show_if_different_values():
    """Test discriminator list items with nested show_if conditions using different values."""
    schema = [{
        'variable': 'items',
        'schema': {
            'type': 'list',
            'items': [{
                'variable': 'entry',
                'schema': {
                    'type': 'dict',
                    'attrs': [
                        {
                            'variable': 'type',
                            'schema': {
                                'type': 'string',
                                'required': True,
                                'default': 'type_a'
                            }
                        },
                        {
                            'variable': 'config',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'type_b']],
                                'attrs': [
                                    {
                                        'variable': 'enable',
                                        'schema': {
                                            'type': 'boolean',
                                            'default': False
                                        }
                                    },
                                    {
                                        'variable': 'field_when_disabled',
                                        'schema': {
                                            'type': 'string',
                                            'show_if': [['enable', '=', False]],
                                            'required': True
                                        }
                                    },
                                    {
                                        'variable': 'field_when_enabled',
                                        'schema': {
                                            'type': 'string',
                                            'show_if': [['enable', '=', True]],
                                            'required': True
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }]
        }
    }]

    # Test with multiple items having different enable values
    values = {
        'items': [
            {
                'type': 'type_b',
                'config': {
                    'enable': False,
                    'field_when_disabled': 'value1'
                }
            },
            {
                'type': 'type_b',
                'config': {
                    'enable': True,
                    'field_when_enabled': 'value2'
                }
            }
        ]
    }

    model = generate_pydantic_model(schema, 'TestDiscriminator', values, NOT_PROVIDED)
    instance = model(**values)

    assert instance.items[0]['config']['enable'] is False
    assert instance.items[0]['config']['field_when_disabled'] == 'value1'
    assert instance.items[1]['config']['enable'] is True
    assert instance.items[1]['config']['field_when_enabled'] == 'value2'


def test_update_scenario_with_discriminator_list():
    """Test update scenario where list items have discriminators and nested show_if."""
    schema = [{
        'variable': 'storage_list',
        'schema': {
            'type': 'list',
            'items': [{
                'variable': 'item',
                'schema': {
                    'type': 'dict',
                    'attrs': [
                        {
                            'variable': 'type',
                            'schema': {
                                'type': 'string',
                                'required': True,
                                'immutable': True,
                                'default': 'type_a'
                            }
                        },
                        {
                            'variable': 'config_a',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'type_a']],
                                'attrs': [
                                    {
                                        'variable': 'field_a',
                                        'schema': {
                                            'type': 'string',
                                            'default': 'default_a'
                                        }
                                    }
                                ]
                            }
                        },
                        {
                            'variable': 'config_b',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'type_b']],
                                'attrs': [
                                    {
                                        'variable': 'toggle',
                                        'schema': {
                                            'type': 'boolean',
                                            'default': False
                                        }
                                    },
                                    {
                                        'variable': 'required_field',
                                        'schema': {
                                            'type': 'string',
                                            'show_if': [['toggle', '=', False]],
                                            'required': True
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }]
        }
    }]

    # Old values
    old_values = {
        'storage_list': [
            {'type': 'type_a', 'config_a': {'field_a': 'old_value'}},
            {'type': 'type_b', 'config_b': {'toggle': False, 'required_field': 'old_required'}}
        ]
    }

    # New values - changing toggle to True (should not require required_field)
    new_values = {
        'storage_list': [
            {'type': 'type_a', 'config_a': {'field_a': 'new_value'}},
            {'type': 'type_b', 'config_b': {'toggle': True}}  # No required_field since toggle=True
        ]
    }

    model = generate_pydantic_model(schema, 'TestUpdate', new_values, old_values)
    instance = model(**new_values)

    assert instance.storage_list[0]['config_a']['field_a'] == 'new_value'
    assert instance.storage_list[1]['config_b']['toggle'] is True


def test_complex_nested_discriminator_with_construct_schema():
    """Test complex nested discriminators using construct_schema."""
    schema = {
        'schema': {
            'questions': [{
                'variable': 'services',
                'schema': {
                    'type': 'dict',
                    'attrs': [{
                        'variable': 'backends',
                        'schema': {
                            'type': 'list',
                            'items': [{
                                'variable': 'backend',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'type',
                                            'schema': {
                                                'type': 'string',
                                                'required': True,
                                                'enum': [
                                                    {'value': 'http'},
                                                    {'value': 'tcp'}
                                                ]
                                            }
                                        },
                                        {
                                            'variable': 'http_config',
                                            'schema': {
                                                'type': 'dict',
                                                'show_if': [['type', '=', 'http']],
                                                'attrs': [
                                                    {
                                                        'variable': 'ssl_enabled',
                                                        'schema': {
                                                            'type': 'boolean',
                                                            'default': False
                                                        }
                                                    },
                                                    {
                                                        'variable': 'port',
                                                        'schema': {
                                                            'type': 'int',
                                                            'show_if': [['ssl_enabled', '=', False]],
                                                            'required': True,
                                                            'default': 80
                                                        }
                                                    },
                                                    {
                                                        'variable': 'ssl_port',
                                                        'schema': {
                                                            'type': 'int',
                                                            'show_if': [['ssl_enabled', '=', True]],
                                                            'required': True,
                                                            'default': 443
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                }
                            }]
                        }
                    }]
                }
            }]
        }
    }

    # Test with multiple backends with different SSL configurations
    values = {
        'services': {
            'backends': [
                {
                    'type': 'http',
                    'http_config': {
                        'ssl_enabled': False,
                        'port': 8080
                    }
                },
                {
                    'type': 'http',
                    'http_config': {
                        'ssl_enabled': True,
                        'ssl_port': 8443
                    }
                }
            ]
        }
    }

    result = construct_schema(schema, values, False)
    assert len(result['verrors'].errors) == 0, \
        f"Should handle different SSL configurations correctly, but got: {result['verrors'].errors}"

    # Test missing required field - but since ssl_port has a default (443), it should pass
    values_with_default = {
        'services': {
            'backends': [{
                'type': 'http',
                'http_config': {
                    'ssl_enabled': True
                    # Missing ssl_port - but has default: 443
                }
            }]
        }
    }

    result_with_default = construct_schema(schema, values_with_default, False)
    assert len(result_with_default['verrors'].errors) == 0, \
        "Should pass when ssl_port is missing but has a default value"

    # Verify the default was applied
    assert result_with_default['new_values']['services']['backends'][0]['http_config']['ssl_port'] == 443


def test_list_items_with_multiple_discriminator_values():
    """Test handling of multiple list items with the same discriminator value."""
    schema = [{
        'variable': 'items',
        'schema': {
            'type': 'list',
            'items': [{
                'variable': 'item',
                'schema': {
                    'type': 'dict',
                    'attrs': [
                        {
                            'variable': 'type',
                            'schema': {
                                'type': 'string',
                                'required': True
                            }
                        },
                        {
                            'variable': 'name',
                            'schema': {
                                'type': 'string',
                                'required': True
                            }
                        },
                        {
                            'variable': 'config_a',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'a']],
                                'attrs': [
                                    {
                                        'variable': 'a_field',
                                        'schema': {
                                            'type': 'string',
                                            'required': True
                                        }
                                    }
                                ]
                            }
                        },
                        {
                            'variable': 'config_b',
                            'schema': {
                                'type': 'dict',
                                'show_if': [['type', '=', 'b']],
                                'attrs': [
                                    {
                                        'variable': 'b_field',
                                        'schema': {
                                            'type': 'string',
                                            'required': True
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }]
        }
    }]

    # Multiple items with same type but different names
    values = {
        'items': [
            {'type': 'a', 'name': 'first_a', 'config_a': {'a_field': 'value1'}},
            {'type': 'a', 'name': 'second_a', 'config_a': {'a_field': 'value2'}},
            {'type': 'b', 'name': 'first_b', 'config_b': {'b_field': 'value3'}},
            {'type': 'a', 'name': 'third_a', 'config_a': {'a_field': 'value4'}}
        ]
    }

    model = generate_pydantic_model(schema, 'TestMultipleDiscriminator', values, NOT_PROVIDED)
    instance = model(**values)

    assert len(instance.items) == 4
    assert instance.items[0]['config_a']['a_field'] == 'value1'
    assert instance.items[1]['config_a']['a_field'] == 'value2'
    assert instance.items[2]['config_b']['b_field'] == 'value3'
    assert instance.items[3]['config_a']['a_field'] == 'value4'
