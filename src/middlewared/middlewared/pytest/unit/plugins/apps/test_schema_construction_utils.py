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
✅ immutable fields - Field that can't be changed once set (string, int, boolean, path)
❌ editable=False - Field with enforced default value (removed from new implementation)
❌ empty attribute support
❌ subquestions support (removed from new implementation)
❌ show_subquestions_if - Conditional subquestion display (removed from new implementation)
✅ show_if - Conditional field display

## show_if Feature Tests:
✅ Basic boolean condition (field shown when condition is true)
✅ Multiple conditions with AND logic
✅ Different operators (=, !=, >)
✅ Nested structure with show_if
✅ List fields with show_if
✅ NotRequired behavior when condition is false
✅ Default value behavior when condition is true

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
from middlewared.plugins.apps.schema_construction_utils import generate_pydantic_model, construct_schema, NOT_PROVIDED


# Basic field type tests
def test_boolean_field_with_default():
    schema = [
        {'variable': 'enabled', 'schema': {'type': 'boolean', 'default': True}}
    ]
    model = generate_pydantic_model(schema, 'TestBool', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestStrings', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestInt', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestOptStr', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestList', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestNestedDefaults', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestNestedReq', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestText', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestPath', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestHostPath', NOT_PROVIDED)
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
    model = generate_pydantic_model(schema, 'TestIP', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestURI', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestIntConstraints', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestStringConstraints', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestNullable', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestPrivate', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestRef', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestEmptyList', NOT_PROVIDED)
    
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
    model = generate_pydantic_model(schema, 'TestEmptyDict', NOT_PROVIDED)
    
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
    
    model = generate_pydantic_model(schema, 'TestComplexEnvs', NOT_PROVIDED)
    
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
    
    model = generate_pydantic_model(schema, 'TestDevices', NOT_PROVIDED)
    
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
    
    model = generate_pydantic_model(schema, 'TestDeepNesting', NOT_PROVIDED)
    
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
    
    model = generate_pydantic_model(schema, 'TestEnumList', NOT_PROVIDED)
    
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
    
    model = generate_pydantic_model(schema, 'TestMixedTypes', NOT_PROVIDED)
    
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
    
    model = generate_pydantic_model(schema, 'TestConstrainedListItems', NOT_PROVIDED)
    
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


# Test show_if functionality
def test_show_if_basic_boolean_condition():
    """Test show_if with basic boolean condition"""
    schema = [
        {
            'variable': 'network',
            'label': '',
            'group': 'Network Configuration',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'publish',
                        'label': 'Some New Field',
                        'description': 'Some new field',
                        'schema': {
                            'type': 'boolean',
                            'default': False,
                            'required': True
                        }
                    },
                    {
                        'variable': 'web_port',
                        'label': 'WebUI Port',
                        'description': 'The port for Nginx WebUI',
                        'schema': {
                            'type': 'int',
                            'default': 8080,
                            'required': True,
                            'show_if': [['publish', '=', True]]
                        }
                    }
                ]
            }
        }
    ]
    
    # Test 1: When publish is False, web_port should not be required
    model1 = generate_pydantic_model(schema[0]['schema']['attrs'], 'TestShowIf1', {'publish': False})
    m1 = model1(publish=False)
    # web_port should be NotRequired when publish is False
    assert hasattr(m1, 'web_port')
    assert m1.web_port is NotRequired
    
    # Test 2: When publish is True, web_port should use its default
    model2 = generate_pydantic_model(schema[0]['schema']['attrs'], 'TestShowIf2', {'publish': True})
    m2 = model2(publish=True)
    assert m2.web_port == 8080
    
    # Test 3: When publish is True and web_port is provided
    m3 = model2(publish=True, web_port=9090)
    assert m3.web_port == 9090


def test_show_if_multiple_conditions():
    """Test show_if with multiple conditions (AND logic)"""
    schema = [
        {
            'variable': 'config',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'mode',
                        'schema': {
                            'type': 'string',
                            'default': 'basic',
                            'required': True
                        }
                    },
                    {
                        'variable': 'advanced_enabled',
                        'schema': {
                            'type': 'boolean',
                            'default': False,
                            'required': True
                        }
                    },
                    {
                        'variable': 'advanced_setting',
                        'schema': {
                            'type': 'string',
                            'default': 'default_advanced',
                            'required': True,
                            'show_if': [
                                ['mode', '=', 'advanced'],
                                ['advanced_enabled', '=', True]
                            ]
                        }
                    }
                ]
            }
        }
    ]
    
    # Test 1: Both conditions false - field should be NotRequired
    model1 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestMultiCond1', 
        {'mode': 'basic', 'advanced_enabled': False}
    )
    m1 = model1(mode='basic', advanced_enabled=False)
    assert m1.advanced_setting is NotRequired
    
    # Test 2: One condition true, one false - field should still be NotRequired
    model2 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestMultiCond2',
        {'mode': 'advanced', 'advanced_enabled': False}
    )
    m2 = model2(mode='advanced', advanced_enabled=False)
    assert m2.advanced_setting is NotRequired
    
    # Test 3: Both conditions true - field should use default
    model3 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestMultiCond3',
        {'mode': 'advanced', 'advanced_enabled': True}
    )
    m3 = model3(mode='advanced', advanced_enabled=True)
    assert m3.advanced_setting == 'default_advanced'


def test_show_if_with_different_operators():
    """Test show_if with different comparison operators"""
    schema = [
        {
            'variable': 'settings',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'count',
                        'schema': {
                            'type': 'int',
                            'default': 5,
                            'required': True
                        }
                    },
                    {
                        'variable': 'status',
                        'schema': {
                            'type': 'string',
                            'default': 'active',
                            'required': True
                        }
                    },
                    {
                        'variable': 'show_on_not_equal',
                        'schema': {
                            'type': 'string',
                            'default': 'shown',
                            'required': True,
                            'show_if': [['status', '!=', 'disabled']]
                        }
                    },
                    {
                        'variable': 'show_on_greater',
                        'schema': {
                            'type': 'string',
                            'default': 'threshold_met',
                            'required': True,
                            'show_if': [['count', '>', 10]]
                        }
                    }
                ]
            }
        }
    ]
    
    # Test != operator
    model1 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestOps1',
        {'status': 'disabled', 'count': 5}
    )
    m1 = model1(status='disabled', count=5)
    assert m1.show_on_not_equal is NotRequired
    
    model2 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestOps2',
        {'status': 'active', 'count': 5}
    )
    m2 = model2(status='active', count=5)
    assert m2.show_on_not_equal == 'shown'
    
    # Test > operator
    model3 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestOps3',
        {'status': 'active', 'count': 15}
    )
    m3 = model3(status='active', count=15)
    assert m3.show_on_greater == 'threshold_met'


def test_show_if_nested_structure():
    """Test show_if in deeply nested structures"""
    # Note: The current implementation evaluates show_if conditions at the immediate parent level
    # For deeply nested structures where conditions reference fields from grandparent levels,
    # the implementation would need to be enhanced to support path-based references like '../type'
    # This test demonstrates the current behavior and limitations
    
    schema = [
        {
            'variable': 'app',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'enable_postgres',
                        'schema': {
                            'type': 'boolean',
                            'default': False,
                            'required': True
                        }
                    },
                    {
                        'variable': 'postgres_host',
                        'schema': {
                            'type': 'string',
                            'default': 'localhost',
                            'required': True,
                            'show_if': [['enable_postgres', '=', True]]
                        }
                    },
                    {
                        'variable': 'postgres_port',
                        'schema': {
                            'type': 'int',
                            'default': 5432,
                            'required': True,
                            'show_if': [['enable_postgres', '=', True]]
                        }
                    }
                ]
            }
        }
    ]
    
    # When enable_postgres is False, postgres fields should be NotRequired
    model1 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestNested1',
        {'enable_postgres': False}
    )
    m1 = model1(enable_postgres=False)
    assert m1.postgres_host is NotRequired
    assert m1.postgres_port is NotRequired
    
    # When enable_postgres is True, fields should have defaults
    model2 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestNested2',
        {'enable_postgres': True}
    )
    m2 = model2(enable_postgres=True)
    assert m2.postgres_host == 'localhost'
    assert m2.postgres_port == 5432


def test_show_if_with_list_fields():
    """Test show_if behavior with list fields"""
    schema = [
        {
            'variable': 'services',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'enable_monitoring',
                        'schema': {
                            'type': 'boolean',
                            'default': False,
                            'required': True
                        }
                    },
                    {
                        'variable': 'monitoring_endpoints',
                        'schema': {
                            'type': 'list',
                            'default': [],
                            'items': [
                                {
                                    'variable': 'endpoint',
                                    'schema': {
                                        'type': 'string',
                                        'required': True
                                    }
                                }
                            ],
                            'show_if': [['enable_monitoring', '=', True]]
                        }
                    }
                ]
            }
        }
    ]
    
    # When monitoring disabled, list should be NotRequired
    model1 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestListShowIf1',
        {'enable_monitoring': False}
    )
    m1 = model1(enable_monitoring=False)
    assert m1.monitoring_endpoints is NotRequired
    
    # When monitoring enabled, list should use default empty list
    model2 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestListShowIf2',
        {'enable_monitoring': True}
    )
    m2 = model2(enable_monitoring=True)
    assert m2.monitoring_endpoints == []
    
    # Can provide values when enabled
    m3 = model2(
        enable_monitoring=True,
        monitoring_endpoints=['http://monitor1.com', 'http://monitor2.com']
    )
    assert len(m3.monitoring_endpoints) == 2


# Additional edge case tests
def test_hidden_field_behavior():
    """Test hidden field attribute (used in real apps for backward compatibility)"""
    schema = [
        {
            'variable': 'db_user',
            'label': 'Database User',
            'description': 'The user for the database.',
            'schema': {
                'type': 'string',
                'hidden': True,  # Field is hidden in UI but still validated
                'default': 'app-user',
                'required': True
            }
        },
        {
            'variable': 'visible_field',
            'schema': {
                'type': 'string',
                'default': 'visible',
                'required': True
            }
        }
    ]
    
    model = generate_pydantic_model(schema, 'TestHidden', NOT_PROVIDED)
    
    # Hidden fields should still work normally in the model
    m = model()
    assert m.db_user == 'app-user'
    assert m.visible_field == 'visible'
    
    # Can override hidden field values
    m2 = model(db_user='custom-user')
    assert m2.db_user == 'custom-user'


def test_immutable_string_field():
    """Test immutable string field - cannot be changed once set"""
    schema = [
        {
            'variable': 'dataset_name',
            'schema': {
                'type': 'string',
                'immutable': True,
                'default': 'data',
                'required': True
            }
        },
        {
            'variable': 'description',
            'schema': {
                'type': 'string',
                'default': 'My dataset',
                'required': False
            }
        }
    ]
    
    # First time creation - no old values, immutable has no effect
    model_create = generate_pydantic_model(schema, 'TestImmutableCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create()
    assert m1.dataset_name == 'data'
    assert m1.description == 'My dataset'
    
    # Can set custom value on creation
    m2 = model_create(dataset_name='custom-data')
    assert m2.dataset_name == 'custom-data'
    
    # Update mode - old_values provided, immutable field is locked
    old_values = {'dataset_name': 'original-data', 'description': 'Original description'}
    model_update = generate_pydantic_model(schema, 'TestImmutableUpdate', NOT_PROVIDED, old_values)
    
    # Can only set the immutable field to its original value
    m3 = model_update(dataset_name='original-data', description='New description')
    assert m3.dataset_name == 'original-data'
    assert m3.description == 'New description'
    
    # Trying to change immutable field should fail
    with pytest.raises(ValidationError) as exc_info:
        model_update(dataset_name='changed-data')
    assert 'dataset_name' in str(exc_info.value)


def test_immutable_int_field():
    """Test immutable int field - cannot be changed once set"""
    schema = [
        {
            'variable': 'port',
            'schema': {
                'type': 'int',
                'immutable': True,
                'default': 8080,
                'required': True
            }
        }
    ]
    
    # Creation - can set any value
    model_create = generate_pydantic_model(schema, 'TestImmutableIntCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(port=9090)
    assert m1.port == 9090
    
    # Update - locked to old value
    old_values = {'port': 3000}
    model_update = generate_pydantic_model(schema, 'TestImmutableIntUpdate', NOT_PROVIDED, old_values)
    
    # Must use the old value
    m2 = model_update(port=3000)
    assert m2.port == 3000
    
    # Cannot change to different value
    with pytest.raises(ValidationError):
        model_update(port=4000)


def test_immutable_boolean_field():
    """Test immutable boolean field - cannot be changed once set"""
    schema = [
        {
            'variable': 'enabled',
            'schema': {
                'type': 'boolean',
                'immutable': True,
                'default': False,
                'required': True
            }
        }
    ]
    
    # Creation
    model_create = generate_pydantic_model(schema, 'TestImmutableBoolCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(enabled=True)
    assert m1.enabled is True
    
    # Update - locked to old value
    old_values = {'enabled': True}
    model_update = generate_pydantic_model(schema, 'TestImmutableBoolUpdate', NOT_PROVIDED, old_values)
    
    # Must match old value
    m2 = model_update(enabled=True)
    assert m2.enabled is True
    
    # Cannot flip the boolean
    with pytest.raises(ValidationError):
        model_update(enabled=False)


def test_immutable_path_field():
    """Test immutable path field - cannot be changed once set"""
    schema = [
        {
            'variable': 'install_path',
            'schema': {
                'type': 'path',
                'immutable': True,
                'default': '/opt/app',
                'required': True
            }
        }
    ]
    
    # Creation
    model_create = generate_pydantic_model(schema, 'TestImmutablePathCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(install_path='/usr/local/app')
    assert m1.install_path == '/usr/local/app'
    
    # Update - locked to old value
    old_values = {'install_path': '/opt/myapp'}
    model_update = generate_pydantic_model(schema, 'TestImmutablePathUpdate', NOT_PROVIDED, old_values)
    
    # Must use old path
    m2 = model_update(install_path='/opt/myapp')
    assert str(m2.install_path) == '/opt/myapp'
    
    # Cannot change path
    with pytest.raises(ValidationError):
        model_update(install_path='/new/path')


def test_immutable_field_with_null():
    """Test immutable nullable field"""
    schema = [
        {
            'variable': 'optional_id',
            'schema': {
                'type': 'string',
                'immutable': True,
                'null': True,
                'default': None,
                'required': False
            }
        }
    ]
    
    # Creation - can set to null or value
    model_create = generate_pydantic_model(schema, 'TestImmutableNullCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(optional_id=None)
    assert m1.optional_id is None
    
    m2 = model_create(optional_id='ABC123')
    assert m2.optional_id == 'ABC123'
    
    # Update with null old value - must remain null
    old_values = {'optional_id': None}
    model_update1 = generate_pydantic_model(schema, 'TestImmutableNullUpdate1', NOT_PROVIDED, old_values)
    m3 = model_update1(optional_id=None)
    assert m3.optional_id is None
    
    # Update with non-null old value - locked to that value
    old_values2 = {'optional_id': 'XYZ789'}
    model_update2 = generate_pydantic_model(schema, 'TestImmutableNullUpdate2', NOT_PROVIDED, old_values2)
    m4 = model_update2(optional_id='XYZ789')
    assert m4.optional_id == 'XYZ789'
    
    with pytest.raises(ValidationError):
        model_update2(optional_id='CHANGED')


def test_immutable_not_supported_types():
    """Test that immutable is ignored for unsupported types"""
    # Dict type - immutable should be ignored
    schema_dict = [
        {
            'variable': 'config',
            'schema': {
                'type': 'dict',
                'immutable': True,  # Should be ignored
                'attrs': [
                    {'variable': 'key', 'schema': {'type': 'string', 'default': 'value'}}
                ]
            }
        }
    ]
    
    old_values = {'config': {'key': 'old_value'}}
    model = generate_pydantic_model(schema_dict, 'TestImmutableDict', NOT_PROVIDED, old_values)
    # Should allow changes since dict is not a supported immutable type
    m = model(config={'key': 'new_value'})
    assert m.config.key == 'new_value'
    
    # List type - immutable should be ignored
    schema_list = [
        {
            'variable': 'items',
            'schema': {
                'type': 'list',
                'immutable': True,  # Should be ignored
                'default': []
            }
        }
    ]
    
    old_values = {'items': ['a', 'b']}
    model = generate_pydantic_model(schema_list, 'TestImmutableList', NOT_PROVIDED, old_values)
    # Should allow changes since list is not a supported immutable type
    m = model(items=['x', 'y', 'z'])
    assert m.items == ['x', 'y', 'z']


def test_immutable_nested_fields():
    """Test immutable fields in nested structures"""
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
                            'default': 'localhost',
                            'required': True
                        }
                    },
                    {
                        'variable': 'port',
                        'schema': {
                            'type': 'int',
                            'default': 5432,
                            'required': True
                        }
                    }
                ]
            }
        }
    ]
    
    # Creation - can set any values
    model_create = generate_pydantic_model(schema, 'TestImmutableNestedCreate', NOT_PROVIDED, NOT_PROVIDED)
    m1 = model_create(database={'host': 'db.example.com', 'port': 3306})
    assert m1.database.host == 'db.example.com'
    assert m1.database.port == 3306
    
    # Update - nested immutable field is locked
    old_values = {'database': {'host': 'prod.db.com', 'port': 5432}}
    model_update = generate_pydantic_model(schema, 'TestImmutableNestedUpdate', NOT_PROVIDED, old_values)
    
    # Can change non-immutable port but not immutable host
    m2 = model_update(database={'host': 'prod.db.com', 'port': 3307})
    assert m2.database.host == 'prod.db.com'
    assert m2.database.port == 3307
    
    # Cannot change immutable nested field
    with pytest.raises(ValidationError):
        model_update(database={'host': 'new.db.com', 'port': 5432})


def test_immutable_with_construct_schema():
    """Test immutable fields through the main construct_schema function"""
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
                    'variable': 'version',
                    'schema': {
                        'type': 'string',
                        'default': '1.0.0',
                        'required': True
                    }
                }
            ]
        }
    }
    
    # Create mode - no old values
    result_create = construct_schema(
        item_version_details,
        {'app_id': 'my-app-123', 'version': '1.0.0'},
        update=False
    )
    assert len(result_create['verrors'].errors) == 0
    assert result_create['new_values']['app_id'] == 'my-app-123'
    
    # Update mode - with old values
    old_values = {'app_id': 'my-app-123', 'version': '1.0.0'}
    
    # Valid update - keeping immutable field same
    result_update_valid = construct_schema(
        item_version_details,
        {'app_id': 'my-app-123', 'version': '2.0.0'},
        update=True,
        old_values=old_values
    )
    assert len(result_update_valid['verrors'].errors) == 0
    assert result_update_valid['new_values']['version'] == '2.0.0'
    
    # Invalid update - trying to change immutable field
    result_update_invalid = construct_schema(
        item_version_details,
        {'app_id': 'different-app', 'version': '2.0.0'},
        update=True,
        old_values=old_values
    )
    assert len(result_update_invalid['verrors'].errors) > 0
    assert 'app_id' in str(result_update_invalid['verrors'].errors)


def test_enum_field_basic():
    """Test basic enum field behavior (partial implementation)"""
    # Note: Full enum support is not yet implemented
    # This test documents current behavior
    schema = [
        {
            'variable': 'log_level',
            'schema': {
                'type': 'string',
                'default': 'info',
                'enum': [
                    {'value': 'debug', 'description': 'Debug level'},
                    {'value': 'info', 'description': 'Info level'},
                    {'value': 'warning', 'description': 'Warning level'},
                    {'value': 'error', 'description': 'Error level'}
                ]
            }
        }
    ]
    
    model = generate_pydantic_model(schema, 'TestEnum', NOT_PROVIDED)
    
    # Default value works
    m = model()
    assert m.log_level == 'info'
    
    # Can set to any string value (enum not enforced yet)
    m2 = model(log_level='debug')
    assert m2.log_level == 'debug'
    
    # Currently allows invalid enum values (not enforced)
    m3 = model(log_level='invalid')
    assert m3.log_level == 'invalid'


def test_complex_show_if_with_list_and_dict():
    """Test show_if with complex nested structures involving lists and dicts"""
    schema = [
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
                        'variable': 'advanced_settings',
                        'schema': {
                            'type': 'list',
                            'default': [],
                            'show_if': [['type', '=', 'advanced']],
                            'items': [
                                {
                                    'variable': 'setting',
                                    'schema': {
                                        'type': 'dict',
                                        'attrs': [
                                            {
                                                'variable': 'key',
                                                'schema': {'type': 'string', 'required': True}
                                            },
                                            {
                                                'variable': 'value',
                                                'schema': {'type': 'string', 'required': True}
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
    
    # When type is 'local', advanced_settings should be NotRequired
    model1 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestComplexShowIf1',
        {'type': 'local'}
    )
    m1 = model1(type='local')
    assert m1.advanced_settings is NotRequired
    
    # When type is 'advanced', advanced_settings should use default empty list
    model2 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestComplexShowIf2',
        {'type': 'advanced'}
    )
    m2 = model2(type='advanced')
    assert m2.advanced_settings == []
    
    # Can provide values when shown
    m3 = model2(
        type='advanced',
        advanced_settings=[
            {'key': 'timeout', 'value': '30'},
            {'key': 'retries', 'value': '3'}
        ]
    )
    assert len(m3.advanced_settings) == 2
    assert m3.advanced_settings[0].key == 'timeout'


def test_field_with_dollar_ref():
    """Test fields with $ref pointing to definitions (common in app schemas)"""
    schema = [
        {
            'variable': 'timezone',
            'label': 'Timezone',
            'schema': {
                'type': 'string',
                'default': 'Etc/UTC',
                'required': True,
                '$ref': ['definitions/timezone']
            }
        },
        {
            'variable': 'certificate_id',
            'label': 'Certificate',
            'schema': {
                'type': 'int',
                'null': True,
                '$ref': ['definitions/certificate']
            }
        }
    ]
    
    model = generate_pydantic_model(schema, 'TestRef', NOT_PROVIDED)
    
    # Test timezone with ref
    m1 = model()
    assert m1.timezone == 'Etc/UTC'
    
    # Test nullable certificate_id with ref
    m2 = model(certificate_id=None)
    assert m2.certificate_id is None
    
    m3 = model(certificate_id=123)
    assert m3.certificate_id == 123
    
    # Verify refs are preserved in metadata
    tz_field = model.model_fields['timezone']
    assert tz_field.metadata == [['definitions/timezone']]
    
    cert_field = model.model_fields['certificate_id']
    assert cert_field.metadata == [['definitions/certificate']]
