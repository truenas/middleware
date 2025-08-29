"""
Comprehensive test coverage for list schemas covering all scenarios:
- Lists without show_if
- Lists with simple schemas
- Lists with complex schemas
- Lists with no item schema
- Lists with nested show_if conditions
- Lists with boolean discriminators
- Lists with string discriminators
"""
from unittest.mock import patch
from middlewared.plugins.apps.schema_construction_utils import construct_schema


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_simple_string_items_no_show_if(mock_isdir, mock_isfile):
    """Test list with simple string items without show_if"""
    app_schema = {
        'questions': [
            {
                'variable': 'tags',
                'label': 'Tags',
                'schema': {
                    'type': 'list',
                    'default': [],
                    'items': [
                        {
                            'variable': 'tag',
                            'label': 'Tag',
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

    # Test with values
    values = {
        'tags': ['production', 'api', 'v1']
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert result['new_values']['tags'] == ['production', 'api', 'v1']

    # Test with empty list
    values = {'tags': []}
    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert result['new_values']['tags'] == []


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_simple_int_items_no_show_if(mock_isdir, mock_isfile):
    """Test list with simple integer items without show_if"""
    app_schema = {
        'questions': [
            {
                'variable': 'ports',
                'label': 'Port Numbers',
                'schema': {
                    'type': 'list',
                    'default': [80, 443],
                    'items': [
                        {
                            'variable': 'port',
                            'label': 'Port',
                            'schema': {
                                'type': 'int',
                                'required': True,
                                'min': 1,
                                'max': 65535
                            }
                        }
                    ]
                }
            }
        ]
    }

    values = {
        'ports': [8080, 8443, 9000]
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert result['new_values']['ports'] == [8080, 8443, 9000]

    # Test validation error for out of range
    values = {'ports': [0]}  # Below min
    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert result['verrors']
    assert 'ports.0' in str(result['verrors'])


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_complex_dict_items_no_show_if(mock_isdir, mock_isfile):
    """Test list with complex dict items without show_if"""
    app_schema = {
        'questions': [
            {
                'variable': 'users',
                'label': 'Users',
                'schema': {
                    'type': 'list',
                    'default': [],
                    'items': [
                        {
                            'variable': 'user',
                            'label': 'User',
                            'schema': {
                                'type': 'dict',
                                'attrs': [
                                    {
                                        'variable': 'username',
                                        'label': 'Username',
                                        'schema': {
                                            'type': 'string',
                                            'required': True
                                        }
                                    },
                                    {
                                        'variable': 'email',
                                        'label': 'Email',
                                        'schema': {
                                            'type': 'string',
                                            'required': True
                                        }
                                    },
                                    {
                                        'variable': 'role',
                                        'label': 'Role',
                                        'schema': {
                                            'type': 'string',
                                            'default': 'user',
                                            'enum': [
                                                {'value': 'admin', 'description': 'Administrator'},
                                                {'value': 'user', 'description': 'Regular User'},
                                                {'value': 'guest', 'description': 'Guest'}
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

    values = {
        'users': [
            {'username': 'john', 'email': 'john@example.com', 'role': 'admin'},
            {'username': 'jane', 'email': 'jane@example.com', 'role': 'user'},
            {'username': 'guest', 'email': 'guest@example.com'}  # Will use default role
        ]
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert len(result['new_values']['users']) == 3
    assert result['new_values']['users'][0]['role'] == 'admin'
    assert result['new_values']['users'][1]['role'] == 'user'
    assert result['new_values']['users'][2]['role'] == 'user'  # Default applied


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_with_no_item_schema(mock_isdir, mock_isfile):
    """Test list with no item schema - just raw values"""
    app_schema = {
        'questions': [
            {
                'variable': 'raw_list',
                'label': 'Raw List',
                'schema': {
                    'type': 'list',
                    'default': ['default1', 'default2']
                    # No items schema - raw list
                }
            }
        ]
    }

    values = {
        'raw_list': ['value1', 'value2', 'value3']
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert result['new_values']['raw_list'] == ['value1', 'value2', 'value3']


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_with_string_discriminator_show_if(mock_isdir, mock_isfile):
    """Test list with string discriminator in show_if conditions"""
    app_schema = {
        'questions': [
            {
                'variable': 'storage_list',
                'label': 'Storage List',
                'schema': {
                    'type': 'list',
                    'default': [],
                    'items': [
                        {
                            'variable': 'storage',
                            'label': 'Storage',
                            'schema': {
                                'type': 'dict',
                                'attrs': [
                                    {
                                        'variable': 'type',
                                        'label': 'Storage Type',
                                        'schema': {
                                            'type': 'string',
                                            'default': 'hostpath',
                                            'enum': [
                                                {'value': 'hostpath', 'description': 'Host Path'},
                                                {'value': 'nfs', 'description': 'NFS'}
                                            ]
                                        }
                                    },
                                    {
                                        'variable': 'path',
                                        'label': 'Path',
                                        'schema': {
                                            'type': 'string',
                                            'required': True,
                                            'show_if': [['type', '=', 'hostpath']]
                                        }
                                    },
                                    {
                                        'variable': 'server',
                                        'label': 'NFS Server',
                                        'schema': {
                                            'type': 'string',
                                            'required': True,
                                            'show_if': [['type', '=', 'nfs']]
                                        }
                                    },
                                    {
                                        'variable': 'share',
                                        'label': 'NFS Share',
                                        'schema': {
                                            'type': 'string',
                                            'required': True,
                                            'show_if': [['type', '=', 'nfs']]
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

    values = {
        'storage_list': [
            {'type': 'hostpath', 'path': '/mnt/data'},
            {'type': 'nfs', 'server': '192.168.1.100', 'share': '/exports/data'}
        ]
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert len(result['new_values']['storage_list']) == 2
    assert result['new_values']['storage_list'][0]['type'] == 'hostpath'
    assert result['new_values']['storage_list'][0]['path'] == '/mnt/data'
    assert result['new_values']['storage_list'][1]['type'] == 'nfs'
    assert result['new_values']['storage_list'][1]['server'] == '192.168.1.100'


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_with_boolean_discriminator_show_if(mock_isdir, mock_isfile):
    """Test list with boolean discriminator in show_if conditions"""
    app_schema = {
        'questions': [
            {
                'variable': 'features',
                'label': 'Features',
                'schema': {
                    'type': 'list',
                    'default': [],
                    'items': [
                        {
                            'variable': 'feature',
                            'label': 'Feature',
                            'schema': {
                                'type': 'dict',
                                'attrs': [
                                    {
                                        'variable': 'name',
                                        'label': 'Feature Name',
                                        'schema': {
                                            'type': 'string',
                                            'required': True
                                        }
                                    },
                                    {
                                        'variable': 'enabled',
                                        'label': 'Enable Feature',
                                        'schema': {
                                            'type': 'boolean',
                                            'default': False
                                        }
                                    },
                                    {
                                        'variable': 'config',
                                        'label': 'Configuration',
                                        'schema': {
                                            'type': 'dict',
                                            'show_if': [['enabled', '=', True]],
                                            'attrs': [
                                                {
                                                    'variable': 'level',
                                                    'label': 'Level',
                                                    'schema': {
                                                        'type': 'int',
                                                        'default': 1,
                                                        'min': 1,
                                                        'max': 10
                                                    }
                                                },
                                                {
                                                    'variable': 'verbose',
                                                    'label': 'Verbose',
                                                    'schema': {
                                                        'type': 'boolean',
                                                        'default': False
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        'variable': 'disabled_reason',
                                        'label': 'Disabled Reason',
                                        'schema': {
                                            'type': 'string',
                                            'default': '',
                                            'show_if': [['enabled', '=', False]]
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

    values = {
        'features': [
            {'name': 'logging', 'enabled': True, 'config': {'level': 5, 'verbose': True}},
            {'name': 'metrics', 'enabled': False, 'disabled_reason': 'Not needed'},
            {'name': 'tracing', 'enabled': True, 'config': {'level': 3}}  # verbose gets default
        ]
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert len(result['new_values']['features']) == 3
    assert result['new_values']['features'][0]['enabled'] is True
    assert result['new_values']['features'][0]['config']['level'] == 5
    assert result['new_values']['features'][1]['enabled'] is False
    assert result['new_values']['features'][1]['disabled_reason'] == 'Not needed'
    assert result['new_values']['features'][2]['config']['verbose'] is False  # Default applied


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_with_nested_show_if_conditions(mock_isdir, mock_isfile):
    """Test list with deeply nested show_if conditions"""
    app_schema = {
        'questions': [
            {
                'variable': 'deployments',
                'label': 'Deployments',
                'schema': {
                    'type': 'list',
                    'default': [],
                    'items': [
                        {
                            'variable': 'deployment',
                            'label': 'Deployment',
                            'schema': {
                                'type': 'dict',
                                'attrs': [
                                    {
                                        'variable': 'environment',
                                        'label': 'Environment',
                                        'schema': {
                                            'type': 'string',
                                            'default': 'dev',
                                            'enum': [
                                                {'value': 'dev', 'description': 'Development'},
                                                {'value': 'prod', 'description': 'Production'}
                                            ]
                                        }
                                    },
                                    {
                                        'variable': 'scaling',
                                        'label': 'Scaling',
                                        'schema': {
                                            'type': 'dict',
                                            'show_if': [['environment', '=', 'prod']],
                                            'attrs': [
                                                {
                                                    'variable': 'enabled',
                                                    'label': 'Enable Auto Scaling',
                                                    'schema': {
                                                        'type': 'boolean',
                                                        'default': False
                                                    }
                                                },
                                                {
                                                    'variable': 'min_replicas',
                                                    'label': 'Minimum Replicas',
                                                    'schema': {
                                                        'type': 'int',
                                                        'default': 2,
                                                        'show_if': [['enabled', '=', True]]
                                                    }
                                                },
                                                {
                                                    'variable': 'max_replicas',
                                                    'label': 'Maximum Replicas',
                                                    'schema': {
                                                        'type': 'int',
                                                        'default': 10,
                                                        'show_if': [['enabled', '=', True]]
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        'variable': 'debug',
                                        'label': 'Debug Settings',
                                        'schema': {
                                            'type': 'dict',
                                            'show_if': [['environment', '=', 'dev']],
                                            'attrs': [
                                                {
                                                    'variable': 'verbose',
                                                    'label': 'Verbose Logging',
                                                    'schema': {
                                                        'type': 'boolean',
                                                        'default': True
                                                    }
                                                },
                                                {
                                                    'variable': 'profiling',
                                                    'label': 'Profiling',
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
            }
        ]
    }

    values = {
        'deployments': [
            {
                'environment': 'prod',
                'scaling': {
                    'enabled': True,
                    'min_replicas': 3,
                    'max_replicas': 20
                }
            },
            {
                'environment': 'dev',
                'debug': {
                    'verbose': True,
                    'profiling': True
                }
            }
        ]
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert len(result['new_values']['deployments']) == 2
    assert result['new_values']['deployments'][0]['scaling']['enabled'] is True
    assert result['new_values']['deployments'][0]['scaling']['min_replicas'] == 3
    assert result['new_values']['deployments'][1]['debug']['profiling'] is True


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_empty_items_with_defaults(mock_isdir, mock_isfile):
    """Test list with empty items but defaults should be applied"""
    app_schema = {
        'questions': [
            {
                'variable': 'configs',
                'label': 'Configurations',
                'schema': {
                    'type': 'list',
                    'default': [],
                    'items': [
                        {
                            'variable': 'config',
                            'label': 'Config',
                            'schema': {
                                'type': 'dict',
                                'attrs': [
                                    {
                                        'variable': 'name',
                                        'label': 'Name',
                                        'schema': {
                                            'type': 'string',
                                            'default': 'default-config'
                                        }
                                    },
                                    {
                                        'variable': 'timeout',
                                        'label': 'Timeout',
                                        'schema': {
                                            'type': 'int',
                                            'default': 30
                                        }
                                    },
                                    {
                                        'variable': 'retry',
                                        'label': 'Retry',
                                        'schema': {
                                            'type': 'boolean',
                                            'default': True
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

    # Provide list with empty dicts - defaults should be applied
    values = {
        'configs': [
            {},  # All defaults
            {'name': 'custom'},  # Partial override
            {'timeout': 60, 'retry': False}  # Different partial override
        ]
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert len(result['new_values']['configs']) == 3
    assert result['new_values']['configs'][0]['name'] == 'default-config'
    assert result['new_values']['configs'][0]['timeout'] == 30
    assert result['new_values']['configs'][0]['retry'] is True
    assert result['new_values']['configs'][1]['name'] == 'custom'
    assert result['new_values']['configs'][1]['timeout'] == 30  # Default applied
    assert result['new_values']['configs'][2]['name'] == 'default-config'  # Default applied
    assert result['new_values']['configs'][2]['timeout'] == 60


@patch('os.path.isfile', return_value=False)
@patch('os.path.isdir', return_value=True)
def test_list_with_multiple_conditions_show_if(mock_isdir, mock_isfile):
    """Test list with multiple show_if conditions (no discriminator)"""
    app_schema = {
        'questions': [
            {
                'variable': 'rules',
                'label': 'Rules',
                'schema': {
                    'type': 'list',
                    'default': [],
                    'items': [
                        {
                            'variable': 'rule',
                            'label': 'Rule',
                            'schema': {
                                'type': 'dict',
                                'attrs': [
                                    {
                                        'variable': 'type',
                                        'label': 'Rule Type',
                                        'schema': {
                                            'type': 'string',
                                            'default': 'basic',
                                            'enum': [
                                                {'value': 'basic', 'description': 'Basic'},
                                                {'value': 'advanced', 'description': 'Advanced'},
                                                {'value': 'custom', 'description': 'Custom'}
                                            ]
                                        }
                                    },
                                    {
                                        'variable': 'priority',
                                        'label': 'Priority',
                                        'schema': {
                                            'type': 'int',
                                            'default': 5,
                                            'min': 1,
                                            'max': 10
                                        }
                                    },
                                    {
                                        'variable': 'advanced_options',
                                        'label': 'Advanced Options',
                                        'schema': {
                                            'type': 'dict',
                                            'show_if': [['type', 'in', ['advanced', 'custom']]],
                                            'attrs': [
                                                {
                                                    'variable': 'threshold',
                                                    'label': 'Threshold',
                                                    'schema': {
                                                        'type': 'int',
                                                        'default': 100
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        'variable': 'high_priority_settings',
                                        'label': 'High Priority Settings',
                                        'schema': {
                                            'type': 'dict',
                                            'show_if': [['priority', '>', 7]],
                                            'attrs': [
                                                {
                                                    'variable': 'immediate',
                                                    'label': 'Immediate Action',
                                                    'schema': {
                                                        'type': 'boolean',
                                                        'default': True
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

    values = {
        'rules': [
            {'type': 'basic', 'priority': 3},  # No extra options
            {'type': 'advanced', 'priority': 8, 'advanced_options': {'threshold': 200}},  # Both conditions met
            {'type': 'custom', 'priority': 5, 'advanced_options': {'threshold': 50}}  # Only advanced_options
        ]
    }

    result = construct_schema(
        item_version_details={'schema': app_schema},
        new_values=values,
        update=False
    )
    assert not result['verrors']
    assert len(result['new_values']['rules']) == 3
    # When there's no discriminator (multiple fields in show_if), the model generation
    # uses actual values from each item, so fields should be present based on conditions
    assert result['new_values']['rules'][1]['advanced_options']['threshold'] == 200
    assert result['new_values']['rules'][2]['advanced_options']['threshold'] == 50
    # Check priority is preserved
    assert result['new_values']['rules'][0]['priority'] == 3
    assert result['new_values']['rules'][1]['priority'] == 8
    assert result['new_values']['rules'][2]['priority'] == 5
