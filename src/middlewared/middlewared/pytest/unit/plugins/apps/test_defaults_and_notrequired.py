"""
Comprehensive tests for default values and NotRequired handling in schema construction.

This module tests various scenarios including:
- Required/optional fields with/without defaults
- show_if conditions with defaults
- Nested structures with complex inheritance
- Edge cases with null values
"""

from middlewared.plugins.apps.schema_construction_utils import construct_schema


def test_required_fields_with_defaults():
    """Test required fields with default values - both provided and not provided by user."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'port',
                    'schema': {
                        'type': 'int',
                        'required': True,
                        'default': 8080
                    }
                },
                {
                    'variable': 'host',
                    'schema': {
                        'type': 'string',
                        'required': True,
                        'default': 'localhost'
                    }
                }
            ]
        }
    }

    # Test with user-provided values
    result = construct_schema(schema, {'port': 9090, 'host': 'example.com'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'port': 9090, 'host': 'example.com'}

    # Test without user-provided values - should use defaults
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'port': 8080, 'host': 'localhost'}

    # Test with partial values
    result = construct_schema(schema, {'port': 3000}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'port': 3000, 'host': 'localhost'}


def test_optional_fields_with_defaults():
    """Test optional fields with default values."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'debug',
                    'schema': {
                        'type': 'boolean',
                        'required': False,
                        'default': False
                    }
                },
                {
                    'variable': 'log_level',
                    'schema': {
                        'type': 'string',
                        'required': False,
                        'default': 'info'
                    }
                }
            ]
        }
    }

    # Test with user-provided values
    result = construct_schema(schema, {'debug': True, 'log_level': 'debug'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'debug': True, 'log_level': 'debug'}

    # Test without user-provided values - should use defaults
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'debug': False, 'log_level': 'info'}

    # Test with partial values
    result = construct_schema(schema, {'debug': True}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'debug': True, 'log_level': 'info'}


def test_optional_fields_without_defaults():
    """Test optional fields without default values - should not appear in output."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'description',
                    'schema': {
                        'type': 'string',
                        'required': False
                    }
                },
                {
                    'variable': 'metadata',
                    'schema': {
                        'type': 'dict',
                        'required': False,
                        'attrs': []
                    }
                }
            ]
        }
    }

    # Test with user-provided values
    result = construct_schema(schema, {'description': 'Test app', 'metadata': {'key': 'value'}}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'description': 'Test app', 'metadata': {'key': 'value'}}

    # Test without user-provided values - dict field gets empty dict default
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'metadata': {}}

    # Test with partial values - dict still gets empty dict default
    result = construct_schema(schema, {'description': 'Test'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'description': 'Test', 'metadata': {}}


def test_show_if_true_with_defaults():
    """Test fields with show_if condition evaluating to true."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'enable_feature',
                    'schema': {
                        'type': 'boolean',
                        'default': True,
                        'required': True
                    }
                },
                {
                    'variable': 'feature_port',
                    'schema': {
                        'type': 'int',
                        'default': 8080,
                        'required': True,
                        'show_if': [['enable_feature', '=', True]]
                    }
                },
                {
                    'variable': 'feature_name',
                    'schema': {
                        'type': 'string',
                        'required': False,
                        'show_if': [['enable_feature', '=', True]]
                    }
                }
            ]
        }
    }

    # Test with feature enabled (explicit)
    result = construct_schema(schema, {'enable_feature': True}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'enable_feature': True, 'feature_port': 8080}

    # Test with feature enabled and all values provided
    result = construct_schema(schema, {
        'enable_feature': True,
        'feature_port': 9090,
        'feature_name': 'MyFeature'
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'enable_feature': True,
        'feature_port': 9090,
        'feature_name': 'MyFeature'
    }

    # Test with default (feature enabled by default)
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'enable_feature': True, 'feature_port': 8080}


def test_show_if_false_with_defaults():
    """Test fields with show_if condition evaluating to false."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'enable_feature',
                    'schema': {
                        'type': 'boolean',
                        'default': False,
                        'required': True
                    }
                },
                {
                    'variable': 'feature_port',
                    'schema': {
                        'type': 'int',
                        'default': 8080,
                        'required': True,
                        'show_if': [['enable_feature', '=', True]]
                    }
                },
                {
                    'variable': 'feature_name',
                    'schema': {
                        'type': 'string',
                        'default': 'DefaultFeature',
                        'required': False,
                        'show_if': [['enable_feature', '=', True]]
                    }
                }
            ]
        }
    }

    # Test with feature disabled (explicit)
    result = construct_schema(schema, {'enable_feature': False}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'enable_feature': False}

    # Test with feature disabled but values provided (values take precedence)
    result = construct_schema(schema, {
        'enable_feature': False,
        'feature_port': 9090,
        'feature_name': 'MyFeature'
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'enable_feature': False,
        'feature_port': 9090,
        'feature_name': 'MyFeature'
    }

    # Test with default (feature disabled by default)
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'enable_feature': False}


def test_nested_show_if_inheritance():
    """Test nested structures with show_if inheritance."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'storage',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'type',
                                'schema': {
                                    'type': 'string',
                                    'default': 'local',
                                    'required': True
                                }
                            },
                            {
                                'variable': 'remote_config',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['type', '=', 'remote']],
                                    'attrs': [
                                        {
                                            'variable': 'host',
                                            'schema': {
                                                'type': 'string',
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'port',
                                            'schema': {
                                                'type': 'int',
                                                'default': 22,
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'username',
                                            'schema': {
                                                'type': 'string',
                                                'required': False
                                            }
                                        }
                                    ]
                                }
                            },
                            {
                                'variable': 'local_config',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['type', '=', 'local']],
                                    'attrs': [
                                        {
                                            'variable': 'path',
                                            'schema': {
                                                'type': 'string',
                                                'default': '/data',
                                                'required': True
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Test with local storage (default)
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'storage': {
            'type': 'local',
            'local_config': {
                'path': '/data'
            }
        }
    }

    # Test with remote storage
    result = construct_schema(schema, {
        'storage': {
            'type': 'remote',
            'remote_config': {
                'host': 'example.com'
            }
        }
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'storage': {
            'type': 'remote',
            'remote_config': {
                'host': 'example.com',
                'port': 22
            }
        }
    }

    # Test with remote storage and optional field
    result = construct_schema(schema, {
        'storage': {
            'type': 'remote',
            'remote_config': {
                'host': 'example.com',
                'username': 'admin'
            }
        }
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'storage': {
            'type': 'remote',
            'remote_config': {
                'host': 'example.com',
                'port': 22,
                'username': 'admin'
            }
        }
    }


def test_complex_nested_structures():
    """Test complex nested structures with multiple levels."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'app',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'name',
                                'schema': {
                                    'type': 'string',
                                    'required': True
                                }
                            },
                            {
                                'variable': 'advanced',
                                'schema': {
                                    'type': 'boolean',
                                    'default': False,
                                    'required': True
                                }
                            },
                            {
                                'variable': 'basic_config',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['advanced', '=', False]],
                                    'attrs': [
                                        {
                                            'variable': 'preset',
                                            'schema': {
                                                'type': 'string',
                                                'default': 'standard',
                                                'required': True
                                            }
                                        }
                                    ]
                                }
                            },
                            {
                                'variable': 'advanced_config',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['advanced', '=', True]],
                                    'attrs': [
                                        {
                                            'variable': 'tuning',
                                            'schema': {
                                                'type': 'dict',
                                                'attrs': [
                                                    {
                                                        'variable': 'cpu_limit',
                                                        'schema': {
                                                            'type': 'int',
                                                            'default': 100,
                                                            'required': True
                                                        }
                                                    },
                                                    {
                                                        'variable': 'memory_limit',
                                                        'schema': {
                                                            'type': 'int',
                                                            'required': False
                                                        }
                                                    }
                                                ]
                                            }
                                        },
                                        {
                                            'variable': 'features',
                                            'schema': {
                                                'type': 'list',
                                                'default': [],
                                                'items': []
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Test basic mode (default)
    result = construct_schema(schema, {'app': {'name': 'MyApp'}}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'app': {
            'name': 'MyApp',
            'advanced': False,
            'basic_config': {
                'preset': 'standard'
            }
        }
    }

    # Test advanced mode
    result = construct_schema(schema, {
        'app': {
            'name': 'MyApp',
            'advanced': True
        }
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'app': {
            'name': 'MyApp',
            'advanced': True,
            'advanced_config': {
                'tuning': {
                    'cpu_limit': 100
                },
                'features': []
            }
        }
    }

    # Test advanced mode with optional memory_limit
    result = construct_schema(schema, {
        'app': {
            'name': 'MyApp',
            'advanced': True,
            'advanced_config': {
                'tuning': {
                    'memory_limit': 2048
                }
            }
        }
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'app': {
            'name': 'MyApp',
            'advanced': True,
            'advanced_config': {
                'tuning': {
                    'cpu_limit': 100,
                    'memory_limit': 2048
                },
                'features': []
            }
        }
    }


def test_list_fields_with_defaults():
    """Test list fields with various default scenarios."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'tags',
                    'schema': {
                        'type': 'list',
                        'default': ['production'],
                        'items': []
                    }
                },
                {
                    'variable': 'ports',
                    'schema': {
                        'type': 'list',
                        'required': False,
                        'items': []
                    }
                },
                {
                    'variable': 'environments',
                    'schema': {
                        'type': 'list',
                        'default': [],
                        'items': [
                            {
                                'variable': 'env',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'name',
                                            'schema': {
                                                'type': 'string',
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'value',
                                            'schema': {
                                                'type': 'string',
                                                'default': '',
                                                'required': True
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Test with defaults - list fields get empty list even if not required
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'tags': ['production'],
        'ports': [],
        'environments': []
    }

    # Test with user values
    result = construct_schema(schema, {
        'tags': ['dev', 'test'],
        'ports': [80, 443],
        'environments': [
            {'name': 'DEBUG', 'value': 'true'},
            {'name': 'LOG_LEVEL'}  # Should use default empty string
        ]
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'tags': ['dev', 'test'],
        'ports': [80, 443],
        'environments': [
            {'name': 'DEBUG', 'value': 'true'},
            {'name': 'LOG_LEVEL', 'value': ''}
        ]
    }


def test_null_vs_not_required():
    """Test distinction between null values and NotRequired."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'nullable_string',
                    'schema': {
                        'type': 'string',
                        'null': True,
                        'required': False
                    }
                },
                {
                    'variable': 'nullable_with_default',
                    'schema': {
                        'type': 'string',
                        'null': True,
                        'default': 'default_value',
                        'required': False
                    }
                },
                {
                    'variable': 'required_nullable',
                    'schema': {
                        'type': 'string',
                        'null': True,
                        'required': True
                    }
                }
            ]
        }
    }

    # Test with null values explicitly set
    result = construct_schema(schema, {
        'nullable_string': None,
        'nullable_with_default': None,
        'required_nullable': None
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'nullable_string': None,
        'nullable_with_default': None,
        'required_nullable': None
    }

    # Test without values - should use defaults where available
    result = construct_schema(schema, {'required_nullable': 'value'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'nullable_with_default': 'default_value',
        'required_nullable': 'value'
    }

    # Test missing required field
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) > 0
    assert 'required_nullable' in str(result['verrors'].errors)


def test_mixed_scenarios():
    """Test complex mixed scenarios combining all features."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'service',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'enabled',
                                'schema': {
                                    'type': 'boolean',
                                    'default': True,
                                    'required': True
                                }
                            },
                            {
                                'variable': 'mode',
                                'schema': {
                                    'type': 'string',
                                    'default': 'auto',
                                    'required': True,
                                    'show_if': [['enabled', '=', True]]
                                }
                            },
                            {
                                'variable': 'manual_config',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['mode', '=', 'manual'], ['enabled', '=', True]],
                                    'attrs': [
                                        {
                                            'variable': 'host',
                                            'schema': {
                                                'type': 'string',
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'port',
                                            'schema': {
                                                'type': 'int',
                                                'default': 8080,
                                                'required': False
                                            }
                                        },
                                        {
                                            'variable': 'ssl',
                                            'schema': {
                                                'type': 'boolean',
                                                'default': False,
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'cert_path',
                                            'schema': {
                                                'type': 'string',
                                                'required': True,
                                                'show_if': [['ssl', '=', True]]
                                            }
                                        }
                                    ]
                                }
                            },
                            {
                                'variable': 'auto_config',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['mode', '=', 'auto'], ['enabled', '=', True]],
                                    'attrs': [
                                        {
                                            'variable': 'discovery_interval',
                                            'schema': {
                                                'type': 'int',
                                                'default': 60,
                                                'required': True
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Test default auto mode
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'service': {
            'enabled': True,
            'mode': 'auto',
            'auto_config': {
                'discovery_interval': 60
            }
        }
    }

    # Test manual mode without SSL
    result = construct_schema(schema, {
        'service': {
            'mode': 'manual',
            'manual_config': {
                'host': 'example.com'
            }
        }
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'service': {
            'enabled': True,
            'mode': 'manual',
            'manual_config': {
                'host': 'example.com',
                'port': 8080,
                'ssl': False
            }
        }
    }

    # Test manual mode with SSL
    result = construct_schema(schema, {
        'service': {
            'mode': 'manual',
            'manual_config': {
                'host': 'example.com',
                'ssl': True,
                'cert_path': '/etc/ssl/cert.pem'
            }
        }
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'service': {
            'enabled': True,
            'mode': 'manual',
            'manual_config': {
                'host': 'example.com',
                'port': 8080,
                'ssl': True,
                'cert_path': '/etc/ssl/cert.pem'
            }
        }
    }

    # Test disabled service
    result = construct_schema(schema, {
        'service': {
            'enabled': False
        }
    }, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'service': {
            'enabled': False
        }
    }


def test_actual_budget_scenario():
    """Test the actual-budget app scenario that exposed the original issue."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'run_as',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'user',
                                'schema': {
                                    'type': 'int',
                                    'default': 568,
                                    'required': True
                                }
                            },
                            {
                                'variable': 'group',
                                'schema': {
                                    'type': 'int',
                                    'default': 568,
                                    'required': True
                                }
                            }
                        ]
                    }
                },
                {
                    'variable': 'network',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'web_port',
                                'schema': {
                                    'type': 'int',
                                    'default': 31012,
                                    'required': True
                                }
                            },
                            {
                                'variable': 'host_network',
                                'schema': {
                                    'type': 'boolean',
                                    'default': False,
                                    'required': True
                                }
                            }
                        ]
                    }
                },
                {
                    'variable': 'storage',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'data',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'type',
                                            'schema': {
                                                'type': 'string',
                                                'default': 'ix_volume',
                                                'required': True
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Test with empty values - should populate all defaults
    result = construct_schema(schema, {}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {
        'run_as': {'user': 568, 'group': 568},
        'network': {'web_port': 31012, 'host_network': False},
        'storage': {'data': {'type': 'ix_volume'}}
    }
