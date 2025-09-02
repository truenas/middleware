import pytest
from pydantic import ValidationError

from middlewared.plugins.apps.schema_construction_utils import (
    construct_schema, generate_pydantic_model, NOT_PROVIDED
)


# ========== Non-List Immutable Field Tests ==========


def test_immutable_string_field():
    """Test basic immutable string field behavior"""
    schema = [
        {
            'variable': 'app_name',
            'schema': {
                'type': 'string',
                'immutable': True,
                'required': True
            }
        }
    ]

    # Create mode - can set any value
    model_create = generate_pydantic_model(schema, 'TestStringCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(app_name='my-application')
    assert m1.app_name == 'my-application'

    # Update mode - field is locked to old value
    old_values = {'app_name': 'original-app'}
    model_update = generate_pydantic_model(schema, 'TestStringUpdate', NOT_PROVIDED, old_values)

    # Can only use the old value
    m2 = model_update(app_name='original-app')
    assert m2.app_name == 'original-app'

    # Cannot change to a different value
    with pytest.raises(ValidationError) as exc_info:
        model_update(app_name='new-app-name')
    assert '1 validation error' in str(exc_info.value)


def test_immutable_int_field():
    """Test basic immutable integer field behavior"""
    schema = [
        {
            'variable': 'port',
            'schema': {
                'type': 'int',
                'immutable': True,
                'required': True
            }
        }
    ]

    # Create mode
    model_create = generate_pydantic_model(schema, 'TestIntCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(port=8080)
    assert m1.port == 8080

    # Update mode
    old_values = {'port': 3000}
    model_update = generate_pydantic_model(schema, 'TestIntUpdate', NOT_PROVIDED, old_values)

    m2 = model_update(port=3000)
    assert m2.port == 3000

    with pytest.raises(ValidationError):
        model_update(port=8080)


def test_immutable_boolean_field():
    """Test basic immutable boolean field behavior"""
    schema = [
        {
            'variable': 'debug_mode',
            'schema': {
                'type': 'boolean',
                'immutable': True,
                'default': False
            }
        }
    ]

    # Create mode
    model_create = generate_pydantic_model(schema, 'TestBoolCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(debug_mode=True)
    assert m1.debug_mode is True

    # Update mode - cannot change boolean value
    old_values = {'debug_mode': True}
    model_update = generate_pydantic_model(schema, 'TestBoolUpdate', NOT_PROVIDED, old_values)

    m2 = model_update(debug_mode=True)
    assert m2.debug_mode is True

    with pytest.raises(ValidationError):
        model_update(debug_mode=False)


def test_immutable_path_field():
    """Test basic immutable path field behavior"""
    schema = [
        {
            'variable': 'data_dir',
            'schema': {
                'type': 'path',
                'immutable': True,
                'required': True
            }
        }
    ]

    # Create mode
    model_create = generate_pydantic_model(schema, 'TestPathCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(data_dir='/mnt/data')
    assert str(m1.data_dir) == '/mnt/data'

    # Update mode
    old_values = {'data_dir': '/opt/app/data'}
    model_update = generate_pydantic_model(schema, 'TestPathUpdate', NOT_PROVIDED, old_values)

    m2 = model_update(data_dir='/opt/app/data')
    assert str(m2.data_dir) == '/opt/app/data'

    with pytest.raises(ValidationError):
        model_update(data_dir='/new/path')


def test_immutable_nested_dict_fields():
    """Test immutable fields in nested dict structures"""
    schema = [
        {
            'variable': 'database',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'host',
                        'schema': {
                            'type': 'string',
                            'immutable': True,
                            'required': True
                        }
                    },
                    {
                        'variable': 'port',
                        'schema': {
                            'type': 'int',
                            'immutable': True,
                            'default': 5432
                        }
                    },
                    {
                        'variable': 'username',
                        'schema': {
                            'type': 'string',
                            'required': True
                        }
                    }
                ]
            }
        }
    ]

    # Create mode - all fields can be set
    model_create = generate_pydantic_model(schema, 'TestNestedDictCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(database={'host': 'db.example.com', 'port': 3306, 'username': 'admin'})
    assert m1.database.host == 'db.example.com'
    assert m1.database.port == 3306

    # Update mode - immutable fields are locked
    old_values = {'database': {'host': 'prod.db.com', 'port': 5432, 'username': 'dbuser'}}
    model_update = generate_pydantic_model(schema, 'TestNestedDictUpdate', NOT_PROVIDED, old_values)

    # Can update non-immutable username
    m2 = model_update(database={'host': 'prod.db.com', 'port': 5432, 'username': 'newuser'})
    assert m2.database.username == 'newuser'

    # Cannot change immutable host
    with pytest.raises(ValidationError):
        model_update(database={'host': 'new.db.com', 'port': 5432, 'username': 'admin'})

    # Cannot change immutable port
    with pytest.raises(ValidationError):
        model_update(database={'host': 'prod.db.com', 'port': 3307, 'username': 'admin'})


def test_immutable_enum_field():
    """Test immutable field with enum constraint"""
    schema = [
        {
            'variable': 'environment',
            'schema': {
                'type': 'string',
                'immutable': True,
                'enum': [
                    {'value': 'development', 'description': 'Development environment'},
                    {'value': 'staging', 'description': 'Staging environment'},
                    {'value': 'production', 'description': 'Production environment'}
                ],
                'required': True
            }
        }
    ]

    # Create mode - can set to any enum value
    model_create = generate_pydantic_model(schema, 'TestEnumCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(environment='production')
    assert m1.environment == 'production'

    # Update mode - locked to old enum value
    old_values = {'environment': 'staging'}
    model_update = generate_pydantic_model(schema, 'TestEnumUpdate', NOT_PROVIDED, old_values)

    # Must use old value
    m2 = model_update(environment='staging')
    assert m2.environment == 'staging'

    # Cannot change to different enum value
    with pytest.raises(ValidationError):
        model_update(environment='production')


def test_immutable_nullable_field():
    """Test immutable field that can be null"""
    schema = [
        {
            'variable': 'license_key',
            'schema': {
                'type': 'string',
                'immutable': True,
                'null': True,
                'default': None
            }
        }
    ]

    # Create mode - can be null or value
    model_create = generate_pydantic_model(schema, 'TestNullableCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(license_key=None)
    assert m1.license_key is None

    m2 = model_create(license_key='ABC-123-XYZ')
    assert m2.license_key == 'ABC-123-XYZ'

    # Update mode - null stays null
    old_values = {'license_key': None}
    model_update1 = generate_pydantic_model(schema, 'TestNullableUpdate1', NOT_PROVIDED, old_values)
    m3 = model_update1(license_key=None)
    assert m3.license_key is None

    # Cannot change null to value
    with pytest.raises(ValidationError):
        model_update1(license_key='NEW-KEY')

    # Update mode - value stays value
    old_values2 = {'license_key': 'XYZ-789'}
    model_update2 = generate_pydantic_model(schema, 'TestNullableUpdate2', NOT_PROVIDED, old_values2)
    m4 = model_update2(license_key='XYZ-789')
    assert m4.license_key == 'XYZ-789'

    # Cannot change value to null
    with pytest.raises(ValidationError):
        model_update2(license_key=None)

    # Cannot change value to different value
    with pytest.raises(ValidationError):
        model_update2(license_key='DIFFERENT')


def test_immutable_with_default_value():
    """Test immutable field with default value"""
    schema = [
        {
            'variable': 'protocol',
            'schema': {
                'type': 'string',
                'immutable': True,
                'default': 'https',
                'required': False
            }
        }
    ]

    # Create mode - can override default
    model_create = generate_pydantic_model(schema, 'TestDefaultCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(protocol='http')
    assert m1.protocol == 'http'

    # Create mode - uses default if not provided
    m2 = model_create()
    assert m2.protocol == 'https'

    # Update mode - locked to old value
    old_values = {'protocol': 'http'}
    model_update = generate_pydantic_model(schema, 'TestDefaultUpdate', NOT_PROVIDED, old_values)

    m3 = model_update(protocol='http')
    assert m3.protocol == 'http'

    with pytest.raises(ValidationError):
        model_update(protocol='https')


def test_multiple_immutable_fields():
    """Test schema with multiple immutable fields"""
    schema = [
        {
            'variable': 'cluster_id',
            'schema': {
                'type': 'string',
                'immutable': True,
                'required': True
            }
        },
        {
            'variable': 'region',
            'schema': {
                'type': 'string',
                'immutable': True,
                'required': True
            }
        },
        {
            'variable': 'instance_count',
            'schema': {
                'type': 'int',
                'default': 1,
                'required': False
            }
        }
    ]

    # Create mode
    model_create = generate_pydantic_model(schema, 'TestMultipleCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(cluster_id='cluster-123', region='us-west-2', instance_count=3)
    assert m1.cluster_id == 'cluster-123'
    assert m1.region == 'us-west-2'

    # Update mode - both immutable fields locked
    old_values = {'cluster_id': 'cluster-456', 'region': 'eu-central-1', 'instance_count': 2}
    model_update = generate_pydantic_model(schema, 'TestMultipleUpdate', NOT_PROVIDED, old_values)

    # Can update mutable field
    m2 = model_update(cluster_id='cluster-456', region='eu-central-1', instance_count=5)
    assert m2.instance_count == 5

    # Cannot change either immutable field
    with pytest.raises(ValidationError):
        model_update(cluster_id='different-cluster', region='eu-central-1', instance_count=3)

    with pytest.raises(ValidationError):
        model_update(cluster_id='cluster-456', region='us-east-1', instance_count=3)


def test_immutable_with_show_if():
    """Test immutable field with show_if condition"""
    schema = [
        {
            'variable': 'enable_advanced',
            'schema': {
                'type': 'boolean',
                'default': False
            }
        },
        {
            'variable': 'advanced_key',
            'schema': {
                'type': 'string',
                'immutable': True,
                'show_if': [['enable_advanced', '=', True]],
                'required': True
            }
        }
    ]

    # Create mode - field visible when condition met
    model_create = generate_pydantic_model(schema, 'TestShowIfCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(enable_advanced=True, advanced_key='secret-123')
    assert m1.advanced_key == 'secret-123'

    # Update mode - immutable field still locked when visible
    old_values = {'enable_advanced': True, 'advanced_key': 'original-key'}
    model_update = generate_pydantic_model(schema, 'TestShowIfUpdate', NOT_PROVIDED, old_values)

    # Can keep same value
    m2 = model_update(enable_advanced=True, advanced_key='original-key')
    assert m2.advanced_key == 'original-key'

    # Cannot change immutable field even with show_if
    with pytest.raises(ValidationError):
        model_update(enable_advanced=True, advanced_key='new-key')


def test_immutable_with_constraints():
    """Test immutable field combined with other constraints"""
    schema = [
        {
            'variable': 'api_key',
            'schema': {
                'type': 'string',
                'immutable': True,
                'min_length': 10,
                'max_length': 50,
                'valid_chars': '^[A-Z0-9-]+$',
                'required': True
            }
        }
    ]

    # Create mode - must satisfy all constraints
    model_create = generate_pydantic_model(schema, 'TestConstraintsCreate', NOT_PROVIDED, NOT_PROVIDED)

    # Valid key
    m1 = model_create(api_key='ABC123-XYZ789')
    assert m1.api_key == 'ABC123-XYZ789'

    # Create mode still validates constraints
    with pytest.raises(ValidationError):  # Too short
        model_create(api_key='ABC')

    with pytest.raises(ValidationError):  # Invalid chars
        model_create(api_key='abc123-xyz789')  # lowercase not allowed

    # Update mode - immutable and constraints
    old_values = {'api_key': 'VALID-KEY-123'}
    model_update = generate_pydantic_model(schema, 'TestConstraintsUpdate', NOT_PROVIDED, old_values)

    # Must use exact old value
    m2 = model_update(api_key='VALID-KEY-123')
    assert m2.api_key == 'VALID-KEY-123'

    # Cannot change even to another valid value
    with pytest.raises(ValidationError):
        model_update(api_key='ANOTHER-VALID-KEY')


def test_immutable_unsupported_types():
    """Test that immutable is ignored for unsupported field types"""
    schema = [
        {
            'variable': 'config_dict',
            'schema': {
                'type': 'dict',
                'immutable': True,  # Should be ignored
                'attrs': [
                    {'variable': 'setting', 'schema': {'type': 'string', 'default': 'value'}}
                ]
            }
        },
        {
            'variable': 'item_list',
            'schema': {
                'type': 'list',
                'immutable': True,  # Should be ignored
                'default': []
            }
        }
    ]

    # Update mode - can change dict and list freely
    old_values = {
        'config_dict': {'setting': 'old'},
        'item_list': ['a', 'b']
    }
    model_update = generate_pydantic_model(schema, 'TestUnsupportedUpdate', NOT_PROVIDED, old_values)

    # Can change dict (immutable ignored)
    m1 = model_update(config_dict={'setting': 'new'}, item_list=['x', 'y', 'z'])
    assert m1.config_dict.setting == 'new'
    assert m1.item_list == ['x', 'y', 'z']


def test_immutable_create_mode_behavior():
    """Test that immutable fields behave normally in create mode"""
    schema = [
        {
            'variable': 'immutable_field',
            'schema': {
                'type': 'string',
                'immutable': True,
                'required': True
            }
        }
    ]

    # Create mode with NOT_PROVIDED old values - no restrictions
    model_create = generate_pydantic_model(schema, 'TestCreateMode', NOT_PROVIDED, NOT_PROVIDED)

    # Can set any value in create mode
    m1 = model_create(immutable_field='value1')
    assert m1.immutable_field == 'value1'

    # Can set different value in another create
    m2 = model_create(immutable_field='value2')
    assert m2.immutable_field == 'value2'


def test_deeply_nested_immutable():
    """Test immutable fields in deeply nested structures"""
    schema = [
        {
            'variable': 'app',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'metadata',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'deployment',
                                    'schema': {
                                        'type': 'dict',
                                        'attrs': [
                                            {
                                                'variable': 'id',
                                                'schema': {
                                                    'type': 'string',
                                                    'immutable': True,
                                                    'required': True
                                                }
                                            },
                                            {
                                                'variable': 'timestamp',
                                                'schema': {
                                                    'type': 'int',
                                                    'immutable': True,
                                                    'required': True
                                                }
                                            },
                                            {
                                                'variable': 'status',
                                                'schema': {
                                                    'type': 'string',
                                                    'default': 'pending'
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

    # Create mode
    model_create = generate_pydantic_model(schema, 'TestDeepCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(app={
        'metadata': {
            'deployment': {
                'id': 'deploy-123',
                'timestamp': 1234567890,
                'status': 'active'
            }
        }
    })
    assert m1.app.metadata.deployment.id == 'deploy-123'

    # Update mode - deeply nested immutable fields locked
    old_values = {
        'app': {
            'metadata': {
                'deployment': {
                    'id': 'deploy-456',
                    'timestamp': 9876543210,
                    'status': 'pending'
                }
            }
        }
    }
    model_update = generate_pydantic_model(schema, 'TestDeepUpdate', NOT_PROVIDED, old_values)

    # Can update non-immutable nested field
    m2 = model_update(app={
        'metadata': {
            'deployment': {
                'id': 'deploy-456',
                'timestamp': 9876543210,
                'status': 'completed'
            }
        }
    })
    assert m2.app.metadata.deployment.status == 'completed'

    # Cannot change deeply nested immutable fields
    with pytest.raises(ValidationError):
        model_update(app={
            'metadata': {
                'deployment': {
                    'id': 'deploy-789',  # Changed
                    'timestamp': 9876543210,
                    'status': 'active'
                }
            }
        })

    with pytest.raises(ValidationError):
        model_update(app={
            'metadata': {
                'deployment': {
                    'id': 'deploy-456',
                    'timestamp': 1111111111,  # Changed
                    'status': 'active'
                }
            }
        })


# ========== Integration Tests with construct_schema ==========


def test_construct_schema_basic_immutable():
    """Test immutable fields through construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'app_id',
                    'schema': {
                        'type': 'string',
                        'immutable': True,
                        'required': True
                    }
                },
                {
                    'variable': 'app_name',
                    'schema': {
                        'type': 'string',
                        'required': True
                    }
                }
            ]
        }
    }

    # Create mode
    result_create = construct_schema(
        item_version_details,
        {'app_id': 'unique-app-123', 'app_name': 'My App'},
        update=False
    )
    assert len(result_create['verrors'].errors) == 0
    assert result_create['new_values']['app_id'] == 'unique-app-123'

    # Update mode - can change app_name but not app_id
    old_values = {'app_id': 'unique-app-123', 'app_name': 'My App'}

    # Valid update
    result_update_valid = construct_schema(
        item_version_details,
        {'app_id': 'unique-app-123', 'app_name': 'My Updated App'},
        update=True,
        old_values=old_values
    )
    assert len(result_update_valid['verrors'].errors) == 0
    assert result_update_valid['new_values']['app_name'] == 'My Updated App'

    # Invalid update - trying to change immutable field
    result_update_invalid = construct_schema(
        item_version_details,
        {'app_id': 'different-id', 'app_name': 'My App'},
        update=True,
        old_values=old_values
    )
    assert len(result_update_invalid['verrors'].errors) > 0


def test_construct_schema_immutable_with_defaults():
    """Test immutable fields with default values in construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'version',
                    'schema': {
                        'type': 'string',
                        'immutable': True,
                        'default': '1.0.0'
                    }
                },
                {
                    'variable': 'auto_update',
                    'schema': {
                        'type': 'boolean',
                        'default': True
                    }
                }
            ]
        }
    }

    # Create without specifying version - uses default
    result_create = construct_schema(
        item_version_details,
        {'auto_update': False},
        update=False
    )
    assert len(result_create['verrors'].errors) == 0
    assert result_create['new_values']['version'] == '1.0.0'

    # Update - version locked to default value
    old_values = {'version': '1.0.0', 'auto_update': False}

    # Try to change version from default
    result_update = construct_schema(
        item_version_details,
        {'version': '2.0.0', 'auto_update': True},
        update=True,
        old_values=old_values
    )
    assert len(result_update['verrors'].errors) > 0
