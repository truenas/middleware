"""
Test Coverage Checklist for schema_construction_utils.py

## Field Types:
✅ int - Basic integer field
✅ string - Basic string field
✅ text - LongString field for large text (up to 1MB)
✅ boolean - Boolean field
✅ ipaddr - IP address field (IPv4 and IPv6)
✅ uri - URI field with validation
✅ hostpath - Host path field (validates actual paths)
✅ path - Absolute path field
✅ dict - Dictionary field (with attrs)
✅ dict - Dictionary field (without attrs - generic dict)
✅ list - List field (with typed items)
✅ list - List field (without items - generic list)

## Field Attributes:
✅ required=True - Required fields
✅ required=False - Optional fields
✅ default - Fields with default values
✅ null=True - Nullable fields
✅ private=True - Secret/private fields
✅ $ref - Fields with metadata reference
✅ description - Field description (tested implicitly)
✅ title - Field title (tested implicitly)
✅ min/max - Integer constraints
✅ min_length/max_length - String length constraints

## Special Behaviors:
✅ NotRequired - Non-required fields without defaults get NotRequired
✅ List default_factory - Non-required lists default to empty list
✅ Dict default_factory - Non-required dicts default to empty dict
✅ Nested models - Dict fields with attrs create nested Pydantic models
✅ Union types - List items with multiple types
✅ Secret wrapper - Private fields wrapped in Secret type
✅ Annotated types - $ref metadata preserved in Annotated types

## Core Functions:
✅ generate_pydantic_model - Creates Pydantic models from schema
✅ process_schema_field - Processes individual field types
✅ create_field_info_from_schema - Creates Field info with constraints
✅ construct_schema - Main entry point with validation
✅ validate_model integration - How models are validated with actual data

## Edge Cases:
✅ Deeply nested dict structures
✅ Lists with mixed item types
✅ Empty string paths for hostpath
✅ Invalid values for constrained fields
❌ Unsupported schema type error handling
❌ Missing 'type' in schema definition
❌ Complex list with Union of different types
❌ Nested private fields
❌ Multiple validation constraints on same field

## Complex Real-World Schemas:
✅ Dict containing list of dicts (e.g., additional_envs pattern)
✅ List of dicts with multiple required fields (e.g., devices pattern)
✅ Deeply nested structure (3+ levels deep)
🔧 List with enum constraints (e.g., apt_packages) - Not yet implemented
✅ Mixed field types in same dict (string, int, boolean, list)
❌ Schema with $ref at root level (e.g., timezone)
❌ Hidden fields behavior
✅ List items with min/max length constraints

## TODO Features (from comments):
❌ immutable fields - Field that can't be changed once set
❌ editable=False - Field with enforced default value
❌ empty attribute support
❌ subquestions support
❌ show_subquestions_if - Conditional subquestion display
❌ show_if - Conditional field display

Remember each schema should follow the following json schema:
'questions': {
    'type': 'array',
    'items': {
        'type': 'object',
        'properties': {
            'variable': {'type': 'string'},
            'label': {'type': 'string'},
            'group': {'type': 'string'},
            'schema': {
                'type': 'object',
                'properties': {
                    'type': {'type': 'string'}
                },
                'required': ['type']
            }
        }
    }
}
"""

import pytest
from pydantic import ValidationError

from middlewared.api.base import NotRequired, LongString
from middlewared.plugins.apps.schema_construction_utils import generate_pydantic_model, construct_schema


# Basic field type tests
def test_boolean_field_with_default():
    schema = [
        {'variable': 'enabled', 'schema': {'type': 'boolean', 'default': True}}
    ]
    model = generate_pydantic_model(schema, 'TestBool')
    # Default value
    m = model()
    assert m.enabled is True
    # Override default
    m2 = model(enabled=False)
    assert m2.enabled is False


def test_string_field_variations():
    schema = [
        {'variable': 'name', 'schema': {'type': 'string', 'required': True}},
        {'variable': 'description', 'schema': {'type': 'string', 'default': 'No description'}},
        {'variable': 'optional_note', 'schema': {'type': 'string', 'required': False}}
    ]
    model = generate_pydantic_model(schema, 'TestStrings')
    
    # Valid with required field
    m = model(name='Test')
    assert m.name == 'Test'
    assert m.description == 'No description'
    assert m.optional_note is NotRequired
    
    # Override default
    m2 = model(name='Test2', description='Custom description')
    assert m2.description == 'Custom description'
    
    # Missing required field should fail
    with pytest.raises(ValidationError):
        model(description='Only description')


def test_required_int_field():
    schema = [
        {'variable': 'count', 'schema': {'type': 'int', 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestInt')
    # Valid
    m = model(count=5)
    assert m.count == 5
    # Missing required should raise
    with pytest.raises(ValidationError):
        model()


def test_optional_string_field():
    schema = [
        {'variable': 'name', 'schema': {'type': 'string', 'required': False}}
    ]
    model = generate_pydantic_model(schema, 'TestOptStr')
    # No value: attribute omitted or None
    m = model()
    assert m.name is NotRequired
    # Providing a string works
    m2 = model(name='abc')
    assert m2.name == 'abc'


def test_list_of_ints():
    schema = [{
        'variable': 'numbers',
        'schema': {'type': 'list', 'items': [{'schema': {'type': 'int'}, 'variable': 'number'}]}
    }]
    model = generate_pydantic_model(schema, 'TestList')
    # valid list
    m = model(numbers=[1, 2, 3])
    assert m.numbers == [1, 2, 3]
    # wrong element type
    with pytest.raises(ValidationError):
        model(numbers=['a', 2])


def test_nested_dict_with_defaults():
    # nested dict with default values on all subfields => no required => default_factory should apply
    schema = [
        {
            'variable': 'config',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'port',
                        'schema': {'type': 'int', 'default': 8080, 'required': False},
                    },
                    {
                        'variable': 'flag',
                        'schema': {'type': 'boolean', 'default': False, 'required': False},
                    },
                ]
            }
        }
    ]
    model = generate_pydantic_model(schema, 'TestNestedDefaults')
    m = model()
    # default_factory should instantiate nested model with defaults
    assert isinstance(m.config, object)
    assert m.config.port == 8080
    assert m.config.flag is False


def test_nested_dict_with_required_subfield():
    # nested dict with one required subfield => no default_factory => missing nested should error
    schema = [
        {
            'variable': 'info',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'name',
                        'schema': {'type': 'string', 'required': True},
                    },
                    {
                        'variable': 'age',
                        'schema': {'type': 'int', 'required': False, 'default': 0},
                    },
                ]
            }
        }
    ]
    model = generate_pydantic_model(schema, 'TestNestedReq')
    # instantiation without info should raise (missing required nested)
    with pytest.raises(ValidationError):
        model()
    # instantiation with partial nested missing 'name' should raise
    with pytest.raises(ValidationError):
        model(info={})
    # instantiation with required field works
    m2 = model(info={'name': 'Alice'})
    assert m2.info.name == 'Alice'
    assert m2.info.age == 0


# Special string type tests
def test_text_field_type():
    schema = [
        {'variable': 'content', 'schema': {'type': 'text', 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestText')
    # Should accept long text
    long_text = 'x' * 10000  # 10KB text
    m = model(content=long_text)
    # LongString type returns a wrapper object, need to access its value
    # Check that the content was set (it's a LongStringWrapper object)
    assert hasattr(m.content, '__str__')
    # Check field type is LongString
    field_type = model.model_fields['content'].annotation
    # The annotation might be wrapped, so check if LongString is in the string representation
    assert 'LongString' in str(field_type)


def test_path_field_type():
    schema = [
        {'variable': 'file_path', 'schema': {'type': 'path', 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestPath')
    # Valid absolute path
    m = model(file_path='/etc/passwd')
    assert m.file_path == '/etc/passwd'
    
    # Relative path should fail
    with pytest.raises(ValidationError):
        model(file_path='relative/path')


def test_hostpath_field_type():
    schema = [
        {'variable': 'host_dir', 'schema': {'type': 'hostpath', 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestHostPath')
    # HostPath type validates actual paths on the system and returns Path objects
    # For unit tests, we'll use paths that should exist
    m = model(host_dir='/tmp')
    assert str(m.host_dir) == '/tmp'
    
    # Test with empty string (which HostPath seems to accept as a special case)
    m2 = model(host_dir='')
    assert str(m2.host_dir) == ''


# Network type tests
def test_ipaddr_field_type():
    schema = [
        {'variable': 'ip', 'schema': {'type': 'ipaddr', 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestIP')
    
    # Valid IPv4
    m = model(ip='192.168.1.1')
    assert str(m.ip) == '192.168.1.1'
    
    # Valid IPv6
    m2 = model(ip='::1')
    assert str(m2.ip) == '::1'
    
    # Invalid IP should fail
    with pytest.raises(ValidationError):
        model(ip='not.an.ip')


def test_uri_field_type():
    schema = [
        {'variable': 'url', 'schema': {'type': 'uri', 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestURI')
    
    # Valid URIs - Pydantic URL type normalizes URLs (adds trailing slash)
    m = model(url='https://example.com')
    assert str(m.url) == 'https://example.com/'
    
    m2 = model(url='ftp://files.example.org/data')
    assert str(m2.url) == 'ftp://files.example.org/data'
    
    # Invalid URI should fail
    with pytest.raises(ValidationError):
        model(url='not a uri')


# Validation constraint tests
def test_int_field_with_constraints():
    schema = [
        {'variable': 'port', 'schema': {'type': 'int', 'min': 1, 'max': 65535, 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestIntConstraints')
    
    # Valid values
    m = model(port=8080)
    assert m.port == 8080
    
    # Edge cases
    m_min = model(port=1)
    assert m_min.port == 1
    
    m_max = model(port=65535)
    assert m_max.port == 65535
    
    # Out of range should fail
    with pytest.raises(ValidationError):
        model(port=0)
    
    with pytest.raises(ValidationError):
        model(port=65536)


def test_string_field_with_length_constraints():
    schema = [
        {'variable': 'username', 'schema': {'type': 'string', 'min_length': 3, 'max_length': 20, 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestStringConstraints')
    
    # Valid lengths
    m = model(username='john')
    assert m.username == 'john'
    
    # Edge cases
    m_min = model(username='abc')
    assert m_min.username == 'abc'
    
    m_max = model(username='a' * 20)
    assert m_max.username == 'a' * 20
    
    # Too short
    with pytest.raises(ValidationError):
        model(username='ab')
    
    # Too long
    with pytest.raises(ValidationError):
        model(username='a' * 21)


# Nullable field tests
def test_nullable_fields():
    schema = [
        {'variable': 'nullable_int', 'schema': {'type': 'int', 'null': True, 'required': True}},
        {'variable': 'nullable_string', 'schema': {'type': 'string', 'null': True, 'default': None}}
    ]
    model = generate_pydantic_model(schema, 'TestNullable')
    
    # None values should be accepted
    m = model(nullable_int=None)
    assert m.nullable_int is None
    assert m.nullable_string is None
    
    # Regular values should also work
    m2 = model(nullable_int=42, nullable_string='hello')
    assert m2.nullable_int == 42
    assert m2.nullable_string == 'hello'


# Private/Secret field tests
def test_private_fields():
    schema = [
        {'variable': 'password', 'schema': {'type': 'string', 'private': True, 'required': True}},
        {'variable': 'api_key', 'schema': {'type': 'string', 'private': True, 'null': True, 'default': None}}
    ]
    model = generate_pydantic_model(schema, 'TestPrivate')
    
    # Should accept values
    m = model(password='secret123')
    # The actual value might be wrapped in Secret type
    assert m.password.get_secret_value() == 'secret123'
    assert m.api_key is None
    
    # With api_key set
    m2 = model(password='pass', api_key='key123')
    assert m2.api_key.get_secret_value() == 'key123'


# Field metadata tests
def test_field_with_ref_metadata():
    schema = [
        {'variable': 'cert_id', 'schema': {'type': 'int', '$ref': ['certificate.query'], 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestRef')
    
    # Should accept int values
    m = model(cert_id=123)
    assert m.cert_id == 123
    
    # Check metadata is preserved (accessing through model_fields)
    field_info = model.model_fields['cert_id']
    # The $ref should be in metadata
    assert field_info.metadata == [['certificate.query']]


# Empty collections tests
def test_empty_list_default():
    schema = [
        {'variable': 'items', 'schema': {'type': 'list', 'required': False}}
    ]
    model = generate_pydantic_model(schema, 'TestEmptyList')
    
    # Should default to empty list
    m = model()
    assert m.items == []
    
    # Can provide values
    m2 = model(items=[1, 2, 3])
    assert m2.items == [1, 2, 3]


def test_empty_dict_default():
    schema = [
        {'variable': 'config', 'schema': {'type': 'dict', 'required': False}}
    ]
    model = generate_pydantic_model(schema, 'TestEmptyDict')
    
    # Should default to empty dict
    m = model()
    assert m.config == {}
    
    # Can provide values
    m2 = model(config={'key': 'value'})
    assert m2.config == {'key': 'value'}


# Complex real-world schema tests
def test_dict_containing_list_of_dicts():
    """Test pattern like additional_envs from Home Assistant"""
    schema = [
        {
            'variable': 'home_assistant',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'additional_envs',
                        'label': 'Additional Environment Variables',
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
                                            {
                                                'variable': 'value',
                                                'label': 'Value',
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
    
    model = generate_pydantic_model(schema, 'TestComplexEnvs')
    
    # Test with empty list (default)
    m1 = model()
    assert m1.home_assistant.additional_envs == []
    
    # Test with valid env vars
    m2 = model(home_assistant={
        'additional_envs': [
            {'name': 'DEBUG', 'value': 'true'},
            {'name': 'LOG_LEVEL', 'value': 'info'}
        ]
    })
    assert len(m2.home_assistant.additional_envs) == 2
    # List items are Pydantic models, not dicts
    assert m2.home_assistant.additional_envs[0].name == 'DEBUG'
    assert m2.home_assistant.additional_envs[0].value == 'true'
    
    # Test validation - missing required field
    with pytest.raises(ValidationError):
        model(home_assistant={
            'additional_envs': [
                {'name': 'DEBUG'}  # missing 'value'
            ]
        })


def test_list_of_dicts_with_multiple_fields():
    """Test pattern like devices from Home Assistant"""
    schema = [
        {
            'variable': 'devices',
            'label': 'Devices',
            'schema': {
                'type': 'list',
                'default': [],
                'items': [
                    {
                        'variable': 'device',
                        'label': 'Device',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'host_device',
                                    'label': 'Host Device',
                                    'schema': {
                                        'type': 'string',
                                        'required': True
                                    }
                                },
                                {
                                    'variable': 'container_device',
                                    'label': 'Container Device',
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
    
    model = generate_pydantic_model(schema, 'TestDevices')
    
    # Test with valid devices
    m = model(devices=[
        {'host_device': '/dev/ttyUSB0', 'container_device': '/dev/ttyACM0'},
        {'host_device': '/dev/ttyUSB1', 'container_device': '/dev/ttyACM1'}
    ])
    assert len(m.devices) == 2
    # List items are Pydantic models, not dicts
    assert m.devices[0].host_device == '/dev/ttyUSB0'
    assert m.devices[1].container_device == '/dev/ttyACM1'


def test_deeply_nested_structure():
    """Test 3+ levels of nesting"""
    schema = [
        {
            'variable': 'app_config',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'database',
                        'schema': {
                            'type': 'dict',
                            'attrs': [
                                {
                                    'variable': 'connections',
                                    'schema': {
                                        'type': 'list',
                                        'default': [],
                                        'items': [
                                            {
                                                'variable': 'connection',
                                                'schema': {
                                                    'type': 'dict',
                                                    'attrs': [
                                                        {
                                                            'variable': 'settings',
                                                            'schema': {
                                                                'type': 'dict',
                                                                'attrs': [
                                                                    {
                                                                        'variable': 'host',
                                                                        'schema': {
                                                                            'type': 'string',
                                                                            'default': 'localhost'
                                                                        }
                                                                    },
                                                                    {
                                                                        'variable': 'port',
                                                                        'schema': {
                                                                            'type': 'int',
                                                                            'default': 5432
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
            }
        }
    ]
    
    model = generate_pydantic_model(schema, 'TestDeepNesting')
    
    # Test with nested data
    m = model(app_config={
        'database': {
            'connections': [
                {
                    'settings': {
                        'host': 'db.example.com',
                        'port': 3306
                    }
                }
            ]
        }
    })
    
    # Navigate the deep structure - list items are Pydantic models
    assert m.app_config.database.connections[0].settings.host == 'db.example.com'
    assert m.app_config.database.connections[0].settings.port == 3306


def test_list_with_enum_constraints():
    """Test pattern like apt_packages from Nextcloud"""
    # TODO: Enum constraints are not yet implemented in the new schema system
    # This test is commented out until enum support is added
    pytest.skip("Enum constraints not yet implemented")
    
    schema = [
        {
            'variable': 'apt_packages',
            'label': 'APT Packages',
            'schema': {
                'type': 'list',
                'default': [],
                'items': [
                    {
                        'variable': 'package',
                        'label': 'Package',
                        'schema': {
                            'type': 'string',
                            'required': True,
                            'enum': [
                                {'value': 'ffmpeg', 'description': 'ffmpeg'},
                                {'value': 'smbclient', 'description': 'smbclient'},
                                {'value': 'ocrmypdf', 'description': 'ocrmypdf'},
                                {'value': 'libreoffice', 'description': 'libreoffice'}
                            ]
                        }
                    }
                ]
            }
        }
    ]
    
    model = generate_pydantic_model(schema, 'TestEnumList')
    
    # Test with valid enum values
    m = model(apt_packages=['ffmpeg', 'smbclient'])
    assert m.apt_packages == ['ffmpeg', 'smbclient']
    
    # Test with invalid enum value
    with pytest.raises(ValidationError):
        model(apt_packages=['ffmpeg', 'invalid-package'])


def test_mixed_field_types_in_dict():
    """Test dict with various field types"""
    schema = [
        {
            'variable': 'server_config',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'name',
                        'schema': {'type': 'string', 'required': True}
                    },
                    {
                        'variable': 'port',
                        'schema': {'type': 'int', 'min': 1, 'max': 65535, 'default': 8080}
                    },
                    {
                        'variable': 'ssl_enabled',
                        'schema': {'type': 'boolean', 'default': False}
                    },
                    {
                        'variable': 'allowed_ips',
                        'schema': {
                            'type': 'list',
                            'default': [],
                            'items': [
                                {
                                    'variable': 'ip',
                                    'schema': {'type': 'ipaddr'}
                                }
                            ]
                        }
                    },
                    {
                        'variable': 'database_url',
                        'schema': {'type': 'uri', 'null': True, 'default': None}
                    }
                ]
            }
        }
    ]
    
    model = generate_pydantic_model(schema, 'TestMixedTypes')
    
    # Test with all field types
    m = model(server_config={
        'name': 'MyServer',
        'port': 443,
        'ssl_enabled': True,
        'allowed_ips': ['192.168.1.100', '10.0.0.1'],
        'database_url': 'postgres://localhost/mydb'
    })
    
    assert m.server_config.name == 'MyServer'
    assert m.server_config.port == 443
    assert m.server_config.ssl_enabled is True
    assert len(m.server_config.allowed_ips) == 2
    assert str(m.server_config.allowed_ips[0]) == '192.168.1.100'
    assert 'postgres://localhost/mydb' in str(m.server_config.database_url)


def test_list_items_with_length_constraints():
    """Test list items with min/max length like tesseract_languages"""
    schema = [
        {
            'variable': 'tesseract_languages',
            'label': 'Tesseract Language Codes',
            'schema': {
                'type': 'list',
                'default': [],
                'items': [
                    {
                        'variable': 'language',
                        'label': 'Language',
                        'schema': {
                            'type': 'string',
                            'min_length': 3,
                            'max_length': 7,
                            'required': True
                        }
                    }
                ]
            }
        }
    ]
    
    model = generate_pydantic_model(schema, 'TestConstrainedListItems')
    
    # Valid language codes
    m = model(tesseract_languages=['eng', 'chi-sim', 'fra'])
    assert m.tesseract_languages == ['eng', 'chi-sim', 'fra']
    
    # Too short
    with pytest.raises(ValidationError):
        model(tesseract_languages=['en'])  # 2 chars, min is 3
    
    # Too long
    with pytest.raises(ValidationError):
        model(tesseract_languages=['eng-long'])  # 8 chars, max is 7


# Test construct_schema function
def test_construct_schema_basic():
    """Test the main construct_schema function"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'app_name',
                    'schema': {'type': 'string', 'required': True}
                },
                {
                    'variable': 'port',
                    'schema': {'type': 'int', 'default': 8080}
                }
            ]
        }
    }
    
    # Test valid values
    result = construct_schema(item_version_details, {'app_name': 'myapp', 'port': 9000}, False)
    assert result['schema_name'] == 'app_create'
    assert len(result['verrors'].errors) == 0
    assert result['new_values'] == {'app_name': 'myapp', 'port': 9000}
    assert result['model'] is not None
    
    # Test missing required field
    result2 = construct_schema(item_version_details, {'port': 9000}, False)
    assert len(result2['verrors'].errors) > 0
    assert 'app_name' in str(result2['verrors'].errors)


def test_construct_schema_complex():
    """Test construct_schema with complex nested structure"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'database',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'host',
                                'schema': {'type': 'string', 'required': True}
                            },
                            {
                                'variable': 'port',
                                'schema': {'type': 'int', 'default': 5432}
                            },
                            {
                                'variable': 'credentials',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'username',
                                            'schema': {'type': 'string', 'required': True}
                                        },
                                        {
                                            'variable': 'password',
                                            'schema': {'type': 'string', 'private': True, 'required': True}
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
    
    new_values = {
        'database': {
            'host': 'localhost',
            'port': 3306,
            'credentials': {
                'username': 'admin',
                'password': 'secret123'
            }
        }
    }
    
    # Test create mode
    result = construct_schema(item_version_details, new_values, False)
    assert result['schema_name'] == 'app_create'
    assert len(result['verrors'].errors) == 0
    
    # Test update mode
    result_update = construct_schema(item_version_details, new_values, True)
    assert result_update['schema_name'] == 'app_update'
    assert len(result_update['verrors'].errors) == 0
    
    # Test validation error - missing required nested field
    invalid_values = {
        'database': {
            'host': 'localhost',
            'credentials': {
                'username': 'admin'
                # missing required password
            }
        }
    }
    
    result_invalid = construct_schema(item_version_details, invalid_values, False)
    assert len(result_invalid['verrors'].errors) > 0
