import pytest

from middlewared.plugins.apps.schema_construction_utils import construct_schema, generate_pydantic_model


@pytest.mark.parametrize('data', [
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
                        'items': [
                            {
                                'variable': 'env',
                                'label': 'Environment Variable',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'name',
                                            'label': 'Name',
                                            'schema': {
                                                'type': 'string',
                                                'required': True
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    },
])
def test_generate_model_success(data):
    # Test that we can generate a Pydantic model from the schema
    model = generate_pydantic_model([data], 'test_model')
    assert model is not None
    assert hasattr(model, '__fields__')
    assert 'actual_budget' in model.__fields__


@pytest.mark.parametrize('data', [
    {
        'variable': 'actual_budget',
        'label': '',
        'group': 'Actual Budget Configuration',
    },
    {
        'variable': 'actual_budget',
        'label': '',
        'group': 'Actual Budget Configuration',
        'schema': {
            'type': 'custom',  # Invalid type
            'attrs': [
                {
                    'variable': 'additional_envs',
                    'label': 'Additional Environment Variables',
                    'description': 'Configure additional environment variables for Actual Budget.',
                    'schema': {
                        'type': 'custom',
                        'default': [],
                        'items': []
                    }
                }
            ]
        }
    }
])
def test_generate_model_invalid_type(data):
    with pytest.raises((KeyError, ValueError)):
        generate_pydantic_model([data], 'test_model')


@pytest.mark.parametrize('data, existing', [
    (
        {
            'variable': 'actual_budget',
            'label': '',
            'group': 'Actual Budget Configuration',
            'schema': {
                'type': 'dict',
                'immutable': True,
                'attrs': [
                    {
                        'variable': 'additional_envs',
                        'label': 'Additional Environment Variables',
                        'description': 'Configure additional environment variables for Actual Budget.',
                        'schema': {
                            'type': 'list',
                            'default': [],
                            'immutable': True,
                            'items': [
                                {
                                    'variable': 'env',
                                    'label': 'Environment Variable',
                                    'schema': {
                                        'type': 'dict',
                                        'attrs': [
                                            {
                                                'variable': 'name',
                                                'label': 'Name',
                                                'schema': {
                                                    'type': 'string',
                                                    'required': True
                                                }
                                            },
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        },
        {
            'actual_budget': {
                'additional_envs': [{'env': {'name': 'EXAMPLE_ENV'}}]
            }
        }
    ),
])
def test_construct_schema_with_existing(data, existing):
    # Test construct_schema with existing values
    item_version_details = {'schema': {'questions': [data]}}
    result = construct_schema(item_version_details, {}, True, existing)
    assert 'verrors' in result
    assert 'new_values' in result
    assert 'schema_name' in result
    assert result['schema_name'] == 'app_update'


@pytest.mark.parametrize('data', [
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
                        'items': [
                            {
                                'variable': 'env',
                                'label': 'Environment Variable',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'name',
                                            'label': 'Name',
                                            'schema': {
                                                'type': 'string',
                                                'enum': [],
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'network',
                                            'label': '',
                                            'group': 'Network Configuration',
                                            'schema': {
                                                'type': 'dict',
                                                'attrs': [
                                                    {
                                                        'variable': 'web_port',
                                                        'label': 'WebUI Port',
                                                        'description': 'The port for Actual Budget WebUI',
                                                        'schema': {
                                                            'type': 'int',
                                                            'default': 31012,
                                                            'required': True,
                                                            '$ref': [
                                                                'definitions/port'
                                                            ],
                                                            'min': 1,
                                                            'max': 65535
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
            ]
        }
    },
])
def test_schema_port_min_max(data):
    # Test that port min/max constraints are handled correctly
    model = generate_pydantic_model([data], 'test_model')
    assert model is not None

    # Create valid instance
    valid_data = {
        'actual_budget': {
            'additional_envs': [{
                'name': 'test',
                'network': {
                    'web_port': 8080
                }
            }]
        }
    }
    instance = model(**valid_data)
    assert instance.actual_budget.additional_envs[0].network.web_port == 8080

    # Test min constraint
    invalid_data = {
        'actual_budget': {
            'additional_envs': [{
                'name': 'test',
                'network': {
                    'web_port': 0  # Below min
                }
            }]
        }
    }
    with pytest.raises(Exception):  # Pydantic validation error
        model(**invalid_data)


@pytest.mark.parametrize('data', [
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
                        'items': [
                            {
                                'variable': 'env',
                                'label': 'Environment Variable',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'name',
                                            'label': 'Name',
                                            'schema': {
                                                'type': 'string',
                                                'valid_chars': '^[a-zA-Z0-9_]+$',
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
    },
])
def test_schema_valid_chars(data):
    # Test that valid_chars constraint works correctly
    model = generate_pydantic_model([data], 'test_model')
    assert model is not None

    # Create valid instance
    valid_data = {
        'actual_budget': {
            'additional_envs': [{
                'name': 'TEST_VAR_123'
            }]
        }
    }
    instance = model(**valid_data)
    assert instance.actual_budget.additional_envs[0].name == 'TEST_VAR_123'

    # Test invalid characters
    invalid_data = {
        'actual_budget': {
            'additional_envs': [{
                'name': 'TEST-VAR'  # Contains dash, not allowed
            }]
        }
    }
    with pytest.raises(Exception):  # Pydantic validation error
        model(**invalid_data)


@pytest.mark.parametrize('data', [
    {
        'variable': 'actual_budget',
        'label': '',
        'group': 'Actual Budget Configuration',
        'schema': {
            'type': 'dict',
            'attrs': [
                {
                    'variable': 'config',
                    'label': 'Configuration',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'enabled',
                                'label': 'Enable Feature',
                                'schema': {
                                    'type': 'boolean',
                                    'default': False
                                }
                            },
                            {
                                'variable': 'advanced_settings',
                                'label': 'Advanced Settings',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['enabled', '=', True]],
                                    'attrs': [
                                        {
                                            'variable': 'debug_mode',
                                            'label': 'Debug Mode',
                                            'schema': {
                                                'type': 'boolean',
                                                'default': False
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
    },
])
def test_schema_show_if_conditions(data):
    # Test that show_if conditions are properly handled
    model = generate_pydantic_model([data], 'test_model')
    assert model is not None

    # When enabled is False, advanced_settings should still be optional
    valid_data = {
        'actual_budget': {
            'config': {
                'enabled': False
            }
        }
    }
    instance = model(**valid_data)
    assert instance.actual_budget.config.enabled is False

    # When enabled is True, advanced_settings can be provided
    valid_data_with_advanced = {
        'actual_budget': {
            'config': {
                'enabled': True,
                'advanced_settings': {
                    'debug_mode': True
                }
            }
        }
    }
    instance = model(**valid_data_with_advanced)
    assert instance.actual_budget.config.enabled is True
    assert instance.actual_budget.config.advanced_settings.debug_mode is True
