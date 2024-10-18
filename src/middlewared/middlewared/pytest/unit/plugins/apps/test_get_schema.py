import pytest

from middlewared.plugins.apps.schema_utils import get_schema, SCHEMA_MAPPING


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
def test_get_schema_success(data):
    result = get_schema(data, False)
    assert result is not None
    valid_types = tuple(v for v in SCHEMA_MAPPING.values() if isinstance(v, type))
    assert isinstance(result[0], valid_types)


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
            'type': 'dict',
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
def test_get_schema_KeyError(data):
    with pytest.raises(KeyError):
        get_schema(data, False)


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
            'actual_budget': {'env': {'name': 'EXAMPLE_ENV', 'value': 'example_value'}}
        }
    ),
])
def test_get_schema_existing(data, existing):
    result = get_schema(data, False, existing)
    assert result is not None
    valid_types = tuple(v for v in SCHEMA_MAPPING.values() if isinstance(v, type))
    assert isinstance(result[0], valid_types)


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
def test_get_schema_port_min_max(data):
    result = get_schema(data, False)
    assert result is not None
    valid_types = tuple(v for v in SCHEMA_MAPPING.values() if isinstance(v, type))
    assert isinstance(result[0], valid_types)


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
                                                'valid_chars': ('char1'),
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
def test_get_schema_valid_chars(data):
    result = get_schema(data, False)
    assert result is not None
    valid_types = tuple(v for v in SCHEMA_MAPPING.values() if isinstance(v, type))
    assert isinstance(result[0], valid_types)


@pytest.mark.parametrize('data', [
    {
        'variable': 'actual_budget',
        'label': '',
        'group': 'Actual Budget Configuration',
        'schema': {
            'type': 'dict',
            'subquestions': [
                {
                    'variable': 'sub_question_1',
                    'schema': {
                        'type': 'dict',
                        'attrs': []
                    }
                },
                {
                    'variable': 'sub_question_2',
                    'schema': {
                        'type': 'dict',
                        'attrs': []
                    }
                }
            ],
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
def test_get_schema_subquestions(data):
    result = get_schema(data, False)
    assert result is not None
    valid_types = tuple(v for v in SCHEMA_MAPPING.values() if isinstance(v, type))
    assert isinstance(result[0], valid_types)
