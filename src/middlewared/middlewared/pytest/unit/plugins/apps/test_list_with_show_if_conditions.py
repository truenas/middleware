"""
Tests for list items with show_if conditions.

These tests verify that list items with conditional fields (show_if) properly
evaluate the conditions based on actual item values, not schema defaults.
"""
import pytest
from pydantic import ValidationError

from middlewared.plugins.apps.schema_construction_utils import (
    generate_pydantic_model, NOT_PROVIDED, construct_schema
)


def test_minio_like_list_with_show_if():
    """
    Test the MinIO-like case where list items have conditional fields based on type.
    This reproduces the bug where 'path' was required even when type='ix_volume'.
    """
    schema = [
        {
            'variable': 'storage',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'data_dirs',
                        'schema': {
                            'type': 'list',
                            'default': [
                                {
                                    'type': 'ix_volume',
                                    'mount_path': '/data1',
                                    'ix_volume_config': {
                                        'dataset_name': 'data1'
                                    }
                                }
                            ],
                            'items': [
                                {
                                    'variable': 'item',
                                    'schema': {
                                        'type': 'dict',
                                        'attrs': [
                                            {
                                                'variable': 'type',
                                                'schema': {
                                                    'type': 'string',
                                                    'required': True,
                                                    'default': 'host_path'  # Default differs from list default
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
                                                            'variable': 'path',
                                                            'schema': {
                                                                'type': 'hostpath',
                                                                'required': True
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
                ]
            }
        }
    ]

    # Test 1: Using defaults (type='ix_volume' in default)
    model = generate_pydantic_model(schema, 'TestMinioDefaults', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model()
    # List items might be dicts or model instances depending on implementation
    assert m1.storage.data_dirs[0]['type'] == 'ix_volume'
    assert m1.storage.data_dirs[0]['ix_volume_config']['dataset_name'] == 'data1'
    # host_path_config should not be required since type='ix_volume'

    # Test 2: User provides ix_volume (should NOT require 'path')
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
    m2 = model(**values)
    assert m2.storage.data_dirs[0].type == 'ix_volume'
    assert m2.storage.data_dirs[0].ix_volume_config.dataset_name == 'data1'

    # Test 3: User provides host_path (should NOT require 'dataset_name')
    values_host = {
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
    model = generate_pydantic_model(schema, 'TestMinioHostPath', values_host, NOT_PROVIDED)
    m3 = model(**values_host)
    assert m3.storage.data_dirs[0].type == 'host_path'
    assert m3.storage.data_dirs[0].host_path_config.path == '/mnt/data'


def test_mixed_show_if_evaluations_in_list():
    """
    Test a list where different items have different show_if evaluations.
    Some items are ix_volume, others are host_path.
    """
    schema = [
        {
            'variable': 'volumes',
            'schema': {
                'type': 'list',
                'items': [
                    {
                        'variable': 'volume',
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
                                    'variable': 'type',
                                    'schema': {
                                        'type': 'string',
                                        'required': True,
                                        'default': 'host_path'
                                    }
                                },
                                {
                                    'variable': 'host_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['type', '=', 'host_path']],
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
                                },
                                {
                                    'variable': 'volume_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['type', '=', 'volume']],
                                        'attrs': [
                                            {
                                                'variable': 'size',
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
        }
    ]

    # Mixed types in the same list
    values = {
        'volumes': [
            {
                'name': 'vol1',
                'type': 'host_path',
                'host_config': {'path': '/mnt/vol1'}
            },
            {
                'name': 'vol2',
                'type': 'volume',
                'volume_config': {'size': '10G'}
            },
            {
                'name': 'vol3',
                'type': 'host_path',
                'host_config': {'path': '/mnt/vol3'}
            }
        ]
    }

    model = generate_pydantic_model(schema, 'TestMixed', values, NOT_PROVIDED)
    m = model(**values)

    assert m.volumes[0].type == 'host_path'
    assert m.volumes[0].host_config.path == '/mnt/vol1'

    assert m.volumes[1].type == 'volume'
    assert m.volumes[1].volume_config.size == '10G'

    assert m.volumes[2].type == 'host_path'
    assert m.volumes[2].host_config.path == '/mnt/vol3'


def test_list_with_show_if_and_immutable():
    """
    Test list items that have both show_if conditions and immutable fields.
    """
    schema = [
        {
            'variable': 'services',
            'schema': {
                'type': 'list',
                'items': [
                    {
                        'variable': 'service',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'id',
                                    'schema': {
                                        'type': 'string',
                                        'required': True,
                                        'immutable': True  # Cannot change after creation
                                    }
                                },
                                {
                                    'variable': 'type',
                                    'schema': {
                                        'type': 'string',
                                        'required': True
                                    }
                                },
                                {
                                    'variable': 'web_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['type', '=', 'web']],
                                        'attrs': [
                                            {
                                                'variable': 'port',
                                                'schema': {
                                                    'type': 'int',
                                                    'required': True
                                                }
                                            }
                                        ]
                                    }
                                },
                                {
                                    'variable': 'db_config',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['type', '=', 'db']],
                                        'attrs': [
                                            {
                                                'variable': 'engine',
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
        }
    ]

    # Create initial services
    old_values = {
        'services': [
            {'id': 'svc1', 'type': 'web', 'web_config': {'port': 8080}},
            {'id': 'svc2', 'type': 'db', 'db_config': {'engine': 'postgres'}}
        ]
    }

    # Update mode - can change type and configs but not id
    new_values = {
        'services': [
            {'id': 'svc1', 'type': 'db', 'db_config': {'engine': 'mysql'}},  # Changed type
            {'id': 'svc2', 'type': 'web', 'web_config': {'port': 3000}}  # Changed type
        ]
    }

    model = generate_pydantic_model(schema, 'TestUpdate', new_values, old_values)
    m = model(**new_values)

    assert m.services[0].id == 'svc1'
    assert m.services[0].type == 'db'
    assert m.services[0].db_config.engine == 'mysql'

    # Try to change immutable field - should fail
    bad_values = {
        'services': [
            {'id': 'changed_id', 'type': 'web', 'web_config': {'port': 8080}},
            {'id': 'svc2', 'type': 'db', 'db_config': {'engine': 'postgres'}}
        ]
    }

    with pytest.raises(ValidationError) as exc_info:
        model(**bad_values)
    assert "Cannot change immutable field 'id'" in str(exc_info.value)


def test_list_show_if_with_defaults_vs_explicit():
    """
    Test that defaults work correctly with show_if in lists,
    and that explicit values override defaults properly.
    """
    schema = [
        {
            'variable': 'config',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'items',
                        'schema': {
                            'type': 'list',
                            'default': [
                                {'mode': 'auto', 'auto_config': {'interval': 60}}
                            ],
                            'items': [
                                {
                                    'variable': 'item',
                                    'schema': {
                                        'type': 'dict',
                                        'attrs': [
                                            {
                                                'variable': 'mode',
                                                'schema': {
                                                    'type': 'string',
                                                    'required': True,
                                                    'default': 'manual'  # Different from list default
                                                }
                                            },
                                            {
                                                'variable': 'manual_config',
                                                'schema': {
                                                    'type': 'dict',
                                                    'show_if': [['mode', '=', 'manual']],
                                                    'attrs': [
                                                        {
                                                            'variable': 'value',
                                                            'schema': {
                                                                'type': 'string',
                                                                'required': True
                                                            }
                                                        }
                                                    ]
                                                }
                                            },
                                            {
                                                'variable': 'auto_config',
                                                'schema': {
                                                    'type': 'dict',
                                                    'show_if': [['mode', '=', 'auto']],
                                                    'attrs': [
                                                        {
                                                            'variable': 'interval',
                                                            'schema': {
                                                                'type': 'int',
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
                ]
            }
        }
    ]

    # Test 1: Use defaults - should use auto mode from list default
    model_defaults = generate_pydantic_model(schema, 'TestDefaults', {}, NOT_PROVIDED)
    m1 = model_defaults()
    assert m1.config.items[0].mode == 'auto'
    assert m1.config.items[0].auto_config.interval == 60

    # Test 2: Override with manual mode
    values = {
        'config': {
            'items': [
                {'mode': 'manual', 'manual_config': {'value': 'test'}}
            ]
        }
    }
    model_explicit = generate_pydantic_model(schema, 'TestExplicit', values, NOT_PROVIDED)
    m2 = model_explicit(**values)
    assert m2.config.items[0].mode == 'manual'
    assert m2.config.items[0].manual_config.value == 'test'


def test_list_show_if_empty_list():
    """
    Test that empty lists work correctly with show_if conditions.
    """
    schema = [
        {
            'variable': 'entries',
            'schema': {
                'type': 'list',
                'items': [
                    {
                        'variable': 'entry',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'enabled',
                                    'schema': {
                                        'type': 'boolean',
                                        'required': True,
                                        'default': True
                                    }
                                },
                                {
                                    'variable': 'settings',
                                    'schema': {
                                        'type': 'dict',
                                        'show_if': [['enabled', '=', True]],
                                        'attrs': [
                                            {
                                                'variable': 'level',
                                                'schema': {
                                                    'type': 'int',
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
    ]

    # Empty list should work fine
    values = {'entries': []}
    model = generate_pydantic_model(schema, 'TestEmpty', values, NOT_PROVIDED)
    m = model(**values)
    assert m.entries == []


def test_nested_show_if_in_list_items():
    """
    Test list items with nested show_if conditions.
    """
    schema = [
        {
            'variable': 'rules',
            'schema': {
                'type': 'list',
                'items': [
                    {
                        'variable': 'rule',
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
                                                    'attrs': [
                                                        {
                                                            'variable': 'case_sensitive',
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
        }
    ]

    # Test nested show_if: filter_config shown when type='filter',
    # and regex_options shown when advanced=True
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
                    # regex_options not required since advanced=False
                }
            },
            {
                'type': 'other'
                # filter_config not required since type != 'filter'
            }
        ]
    }

    model = generate_pydantic_model(schema, 'TestNested', values, NOT_PROVIDED)
    m = model(**values)

    assert m.rules[0].filter_config.pattern == '*.txt'
    assert m.rules[0].filter_config.regex_options.case_sensitive is False

    assert m.rules[1].filter_config.pattern == '*.log'
    # regex_options should not be present or should be optional

    assert m.rules[2].type == 'other'
    # filter_config should not be required


def test_construct_schema_with_list_show_if():
    """
    Test list with show_if through the main construct_schema function.
    This ensures the complete validation pipeline works correctly.
    """
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'storage',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'volumes',
                                'schema': {
                                    'type': 'list',
                                    'default': [],
                                    'items': [
                                        {
                                            'variable': 'volume',
                                            'schema': {
                                                'type': 'dict',
                                                'attrs': [
                                                    {
                                                        'variable': 'type',
                                                        'schema': {
                                                            'type': 'string',
                                                            'required': True,
                                                            'default': 'host'
                                                        }
                                                    },
                                                    {
                                                        'variable': 'host_path',
                                                        'schema': {
                                                            'type': 'string',
                                                            'show_if': [['type', '=', 'host']],
                                                            'required': True
                                                        }
                                                    },
                                                    {
                                                        'variable': 'volume_name',
                                                        'schema': {
                                                            'type': 'string',
                                                            'show_if': [['type', '=', 'volume']],
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
            ]
        }
    }

    # Test with volume type (should not require host_path)
    new_values = {
        'storage': {
            'volumes': [
                {'type': 'volume', 'volume_name': 'my-volume'}
            ]
        }
    }

    result = construct_schema(item_version_details, new_values, False)
    assert not result['verrors']
    assert result['new_values']['storage']['volumes'][0]['type'] == 'volume'
    assert result['new_values']['storage']['volumes'][0]['volume_name'] == 'my-volume'

    # Test with host type (should not require volume_name)
    new_values_host = {
        'storage': {
            'volumes': [
                {'type': 'host', 'host_path': '/mnt/data'}
            ]
        }
    }

    result_host = construct_schema(item_version_details, new_values_host, False)
    assert not result_host['verrors']
    assert result_host['new_values']['storage']['volumes'][0]['type'] == 'host'
    assert result_host['new_values']['storage']['volumes'][0]['host_path'] == '/mnt/data'
