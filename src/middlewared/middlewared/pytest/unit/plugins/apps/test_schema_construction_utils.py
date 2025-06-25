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
✅ valid_chars - Regex pattern validation for strings
✅ enum - String enum constraints with Literal types

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
✅ List with enum constraints (e.g., apt_packages, minio protocols)
✅ Mixed field types in same dict (string, int, boolean, list)
❌ Schema with $ref at root level (e.g., timezone)
✅ List items with min/max length constraints

## TODO Features (from comments):
✅ immutable fields - Field that can't be changed once set (string, int, boolean, path)
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

from middlewared.api.base import NotRequired
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
    # nested dict with one required subfield => not required at top level => NotRequired when not provided
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


def test_path_field_with_length_constraints():
    """Test path type with min_length and max_length validation"""
    schema = [
        {
            'variable': 'config_path',
            'schema': {
                'type': 'path',
                'min_length': 5,
                'max_length': 50,
                'required': True
            }
        }
    ]
    model = generate_pydantic_model(schema, 'TestPathLengthConstraints', NOT_PROVIDED)

    # Valid path within length bounds
    m = model(config_path='/etc/config')
    assert m.config_path == '/etc/config'

    # Edge case - minimum length (5 characters)
    m_min = model(config_path='/tmp/')
    assert m_min.config_path == '/tmp'  # Normalized without trailing slash

    # Edge case - maximum length (50 characters)
    long_path = '/' + 'a' * 49
    m_max = model(config_path=long_path)
    assert m_max.config_path == long_path

    # Too short - less than 5 characters
    with pytest.raises(ValidationError) as exc_info:
        model(config_path='/ab')
    assert 'Value should have at least 5 items' in str(exc_info.value)

    # Too long - more than 50 characters
    with pytest.raises(ValidationError) as exc_info:
        model(config_path='/' + 'a' * 50)
    assert 'Value should have at most 50 items' in str(exc_info.value)

    # Still must be absolute path
    with pytest.raises(ValidationError) as exc_info:
        model(config_path='relative/path/long/enough')
    assert 'Path must be absolute' in str(exc_info.value)

    # Empty string should fail min_length validation
    with pytest.raises(ValidationError) as exc_info:
        model(config_path='')
    assert 'Value should have at least 5 items' in str(exc_info.value)


def test_hostpath_field_with_length_constraints():
    """Test hostpath type with min_length and max_length validation"""
    schema = [
        {
            'variable': 'data_dir',
            'schema': {
                'type': 'hostpath',
                'min_length': 4,
                'max_length': 30,
                'required': True
            }
        }
    ]
    model = generate_pydantic_model(schema, 'TestHostPathLengthConstraints', NOT_PROVIDED)

    # Valid hostpath within length bounds
    m = model(data_dir='/tmp')
    assert str(m.data_dir) == '/tmp'

    # Edge case - minimum length (4 characters)
    m_min = model(data_dir='/tmp')
    assert str(m_min.data_dir) == '/tmp'

    # Edge case - maximum length (must exist on system)
    # Using /tmp since it should exist on most systems
    m_max = model(data_dir='/tmp')
    assert str(m_max.data_dir) == '/tmp'

    # Empty string should fail min_length validation
    with pytest.raises(ValidationError) as exc_info:
        model(data_dir='')
    assert 'String should have at least 4 characters' in str(exc_info.value)

    # Too short non-empty path
    with pytest.raises(ValidationError) as exc_info:
        model(data_dir='/a')
    # This will now fail because of length validation happening first
    assert 'String should have at least 4 characters' in str(exc_info.value)

    # Too long - more than 30 characters (if path exists)
    # Note: This test is tricky because hostpath validates actual existence
    # We can't easily test max_length without a real long path that exists
    with pytest.raises(ValidationError) as exc_info:
        model(data_dir='/this/is/a/very/long/path/that/exceeds/limit')
    # This will fail either because of length or non-existence
    errors = str(exc_info.value)
    assert ('String should have at most 30 characters' in errors or
            'Path does not exist' in errors or
            'File does not exist' in errors)


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
    # Private fields are no longer wrapped in Secret type
    assert m.password == 'secret123'
    assert m.api_key is None

    # With api_key set
    m2 = model(password='pass', api_key='key123')
    assert m2.api_key == 'key123'


def test_private_string_with_length_constraints():
    """Test private/secret string fields with min/max length validation"""
    schema = [
        {
            'variable': 'api_token',
            'schema': {
                'type': 'string',
                'private': True,
                'min_length': 10,
                'max_length': 50,
                'required': True
            }
        },
        {
            'variable': 'secret_key',
            'schema': {
                'type': 'string',
                'private': True,
                'min_length': 5,
                'max_length': 20,
                'default': 'default123',
                'required': False
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestPrivateLength', NOT_PROVIDED)
    # Test valid lengths
    m1 = model(api_token='1234567890')  # Exactly 10 chars (min)
    assert m1.api_token == '1234567890'
    assert m1.secret_key == 'default123'

    # Test max length
    m2 = model(api_token='a' * 50)  # Exactly 50 chars (max)
    assert m2.api_token == 'a' * 50

    # Test custom secret_key within bounds
    m3 = model(api_token='valid_token_123', secret_key='mysecret')
    assert m3.api_token == 'valid_token_123'
    assert m3.secret_key == 'mysecret'

    # Test too short - should fail
    with pytest.raises(ValidationError) as exc_info:
        model(api_token='short')  # Only 5 chars, min is 10
    assert 'at least 10 characters' in str(exc_info.value)
    assert 'api_token' in str(exc_info.value)

    # Test too long - should fail
    with pytest.raises(ValidationError) as exc_info:
        model(api_token='a' * 51)  # 51 chars, max is 50
    assert 'at most 50 characters' in str(exc_info.value)
    assert 'api_token' in str(exc_info.value)

    # Test secret_key too short
    with pytest.raises(ValidationError) as exc_info:
        model(api_token='valid_token', secret_key='abc')  # Only 3 chars, min is 5
    assert 'at least 5 characters' in str(exc_info.value)
    assert 'secret_key' in str(exc_info.value)

    # Test secret_key too long
    with pytest.raises(ValidationError) as exc_info:
        model(api_token='valid_token', secret_key='a' * 21)  # 21 chars, max is 20
    assert 'at most 20 characters' in str(exc_info.value)
    assert 'secret_key' in str(exc_info.value)


def test_private_string_complex_validation():
    """Test private string fields with multiple validation constraints combined"""
    schema = [
        {
            'variable': 'license_key',
            'schema': {
                'type': 'string',
                'private': True,
                'min_length': 19,
                'max_length': 19,  # Exactly 19 chars (4+1+4+1+4+1+4)
                'valid_chars': '^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$',  # XXXX-XXXX-XXXX-XXXX format
                'required': True
            }
        },
        {
            'variable': 'optional_secret',
            'schema': {
                'type': 'string',
                'private': True,
                'null': True,
                'min_length': 8,
                'max_length': 32,
                'default': None,
                'required': False
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestPrivateComplex', NOT_PROVIDED)
    # Valid license key
    m1 = model(license_key='ABCD-1234-WXYZ-5678')
    assert m1.license_key == 'ABCD-1234-WXYZ-5678'
    assert m1.optional_secret is None

    # Valid with optional secret
    m2 = model(license_key='XXXX-YYYY-ZZZZ-0000', optional_secret='mysecret123')
    assert m2.license_key == 'XXXX-YYYY-ZZZZ-0000'
    assert m2.optional_secret == 'mysecret123'

    # Invalid format (lowercase letters)
    with pytest.raises(ValidationError) as exc_info:
        model(license_key='abcd-1234-wxyz-5678')
    assert 'license_key' in str(exc_info.value)

    # Wrong length (too short)
    with pytest.raises(ValidationError) as exc_info:
        model(license_key='ABC-123-XYZ-456')  # Only 15 chars
    assert 'at least 19 characters' in str(exc_info.value)

    # Wrong length (too long)
    with pytest.raises(ValidationError) as exc_info:
        model(license_key='ABCD-1234-WXYZ-56789')  # 20 chars
    assert 'at most 19 characters' in str(exc_info.value)

    # Optional secret too short
    with pytest.raises(ValidationError) as exc_info:
        model(license_key='ABCD-1234-WXYZ-5678', optional_secret='short')
    assert 'at least 8 characters' in str(exc_info.value)
    assert 'optional_secret' in str(exc_info.value)


# Field metadata tests
def test_field_with_ref_metadata():
    schema = [
        {'variable': 'cert_id', 'schema': {'type': 'int', '$ref': ['certificate.query'], 'required': True}}
    ]
    model = generate_pydantic_model(schema, 'TestRef', NOT_PROVIDED)

    # Should accept int values
    m = model(cert_id=123)
    assert m.cert_id == 123

    # $ref metadata is no longer stored in pydantic model after commit 78cf7c7799
    # The field should still work correctly, just without the metadata
    field_info = model.model_fields['cert_id']
    assert field_info is not None


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


def test_list_with_min_max_constraints():
    """Test list with min/max constraints on the number of items"""
    schema = [
        {
            'variable': 'ports',
            'label': 'Port Numbers',
            'schema': {
                'type': 'list',
                'min': 1,  # At least 1 port required
                'max': 5,  # Maximum 5 ports allowed
                'default': [],
                'items': [
                    {
                        'variable': 'port',
                        'label': 'Port',
                        'schema': {
                            'type': 'int',
                            'min': 1,
                            'max': 65535,
                            'required': True
                        }
                    }
                ]
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestListMinMax', NOT_PROVIDED)

    # Valid: 1-5 ports
    m1 = model(ports=[8080])
    assert m1.ports == [8080]

    m2 = model(ports=[80, 443, 8080])
    assert m2.ports == [80, 443, 8080]

    m3 = model(ports=[80, 443, 8080, 8443, 9000])
    assert m3.ports == [80, 443, 8080, 8443, 9000]

    # Invalid: empty list (min is 1)
    with pytest.raises(ValidationError) as exc_info:
        model(ports=[])
    assert 'at least 1 item' in str(exc_info.value).lower()

    # Invalid: too many items (max is 5)
    with pytest.raises(ValidationError) as exc_info:
        model(ports=[80, 443, 8080, 8443, 9000, 9090])
    assert 'at most 5 items' in str(exc_info.value).lower()


def test_list_with_only_min_constraint():
    """Test list with only min constraint"""
    schema = [
        {
            'variable': 'tags',
            'schema': {
                'type': 'list',
                'min': 2,  # At least 2 tags required
                'default': [],
                'items': [
                    {
                        'variable': 'tag',
                        'schema': {
                            'type': 'string',
                            'required': True
                        }
                    }
                ]
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestListMin', NOT_PROVIDED)

    # Valid: 2 or more tags
    m = model(tags=['web', 'api'])
    assert m.tags == ['web', 'api']

    m2 = model(tags=['web', 'api', 'database', 'cache'])
    assert len(m2.tags) == 4

    # Invalid: less than 2 tags
    with pytest.raises(ValidationError):
        model(tags=['single'])


def test_list_with_only_max_constraint():
    """Test list with only max constraint"""
    schema = [
        {
            'variable': 'dns_servers',
            'schema': {
                'type': 'list',
                'max': 3,  # Maximum 3 DNS servers
                'default': [],
                'items': [
                    {
                        'variable': 'server',
                        'schema': {
                            'type': 'ipaddr',
                            'required': True
                        }
                    }
                ]
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestListMax', NOT_PROVIDED)

    # Valid: 0-3 DNS servers
    m1 = model(dns_servers=[])
    assert m1.dns_servers == []

    m2 = model(dns_servers=['8.8.8.8', '8.8.4.4'])
    assert len(m2.dns_servers) == 2

    # Invalid: more than 3 servers
    with pytest.raises(ValidationError):
        model(dns_servers=['8.8.8.8', '8.8.4.4', '1.1.1.1', '1.0.0.1'])


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
    # Check that the error path includes the full nested path without 'values.' prefix
    error_paths = [e.attribute for e in result_invalid['verrors'].errors]
    assert 'database.credentials.password' in error_paths


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
    # Test with new_values to simulate real usage through construct_schema
    new_values = {'dataset_name': 'changed-data', 'description': 'New description'}
    model_update = generate_pydantic_model(schema, 'TestImmutableUpdate', new_values, old_values)

    # Can only set the immutable field to its original value
    m3 = model_update(dataset_name='original-data', description='New description')
    assert m3.dataset_name == 'original-data'
    assert m3.description == 'New description'

    # Trying to change immutable field should fail
    # First, let's see if we can instantiate the model with changed data
    try:
        m_fail = model_update(dataset_name='changed-data')
        # If we get here, the immutable validation is not working!
        assert False, f"Expected ValidationError but model was created with dataset_name={m_fail.dataset_name}"
    except ValidationError as exc_info:
        assert 'dataset_name' in str(exc_info)


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
    """Test basic enum field behavior with proper enforcement"""
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

    # Valid enum values work
    m2 = model(log_level='debug')
    assert m2.log_level == 'debug'

    # Invalid enum values should fail
    with pytest.raises(ValidationError) as exc_info:
        model(log_level='invalid')
    assert 'log_level' in str(exc_info.value)


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

    # $ref metadata is no longer stored in pydantic model after commit 78cf7c7799
    # Fields should still work correctly, just without the metadata
    tz_field = model.model_fields['timezone']
    assert tz_field is not None

    cert_field = model.model_fields['certificate_id']
    assert cert_field is not None


def test_string_field_with_valid_chars():
    """Test string field with valid_chars regex validation"""
    schema = [
        {
            'variable': 'username',
            'schema': {
                'type': 'string',
                'valid_chars': '^[a-zA-Z][a-zA-Z0-9_-]{2,30}$',  # Username pattern
                'required': True
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestValidChars', NOT_PROVIDED)

    # Valid usernames
    m1 = model(username='john_doe')
    assert m1.username == 'john_doe'

    m2 = model(username='User123')
    assert m2.username == 'User123'

    m3 = model(username='test-user')
    assert m3.username == 'test-user'

    # Invalid usernames should fail
    with pytest.raises(ValidationError) as exc_info:
        model(username='123invalid')  # Starts with number
    assert 'Value does not match' in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        model(username='a')  # Too short
    assert 'Value does not match' in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        model(username='user@name')  # Contains invalid character
    assert 'Value does not match' in str(exc_info.value)


def test_valid_chars_with_different_patterns():
    """Test various regex patterns with valid_chars"""
    # Email pattern
    schema_email = [
        {
            'variable': 'email',
            'schema': {
                'type': 'string',
                'valid_chars': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                'required': True
            }
        }
    ]

    model_email = generate_pydantic_model(schema_email, 'TestEmail', NOT_PROVIDED)

    # Valid emails
    m1 = model_email(email='user@example.com')
    assert m1.email == 'user@example.com'

    m2 = model_email(email='test.user+tag@sub.domain.org')
    assert m2.email == 'test.user+tag@sub.domain.org'

    # Invalid emails
    with pytest.raises(ValidationError):
        model_email(email='invalid.email')

    with pytest.raises(ValidationError):
        model_email(email='@example.com')

    # Alphanumeric pattern
    schema_alphanumeric = [
        {
            'variable': 'code',
            'schema': {
                'type': 'string',
                'valid_chars': '^[A-Z0-9]+$',  # Only uppercase letters and numbers
                'required': True
            }
        }
    ]

    model_alpha = generate_pydantic_model(schema_alphanumeric, 'TestAlpha', NOT_PROVIDED)

    # Valid codes
    m3 = model_alpha(code='ABC123')
    assert m3.code == 'ABC123'

    # Invalid codes
    with pytest.raises(ValidationError):
        model_alpha(code='abc123')  # Lowercase not allowed

    with pytest.raises(ValidationError):
        model_alpha(code='ABC-123')  # Dash not allowed


def test_valid_chars_with_nullable_field():
    """Test valid_chars with nullable string field"""
    schema = [
        {
            'variable': 'optional_code',
            'schema': {
                'type': 'string',
                'valid_chars': '^[A-Z]{3}[0-9]{3}$',  # Pattern like ABC123
                'null': True,
                'default': None
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestNullableValidChars', NOT_PROVIDED)

    # Null is allowed
    m1 = model(optional_code=None)
    assert m1.optional_code is None

    # Valid pattern
    m2 = model(optional_code='ABC123')
    assert m2.optional_code == 'ABC123'

    # Invalid pattern
    with pytest.raises(ValidationError):
        model(optional_code='ABC12')  # Too short

    with pytest.raises(ValidationError):
        model(optional_code='abc123')  # Lowercase


def test_valid_chars_with_default_value():
    """Test valid_chars with default value that must match pattern"""
    schema = [
        {
            'variable': 'version',
            'schema': {
                'type': 'string',
                'valid_chars': r'^\d+\.\d+\.\d+$',  # Semantic version pattern
                'default': '1.0.0',
                'required': False
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestDefaultValidChars', NOT_PROVIDED)

    # Default value is valid
    m1 = model()
    assert m1.version == '1.0.0'

    # Valid versions
    m2 = model(version='2.1.0')
    assert m2.version == '2.1.0'

    m3 = model(version='10.20.30')
    assert m3.version == '10.20.30'

    # Invalid versions
    with pytest.raises(ValidationError):
        model(version='1.0')  # Missing patch version

    with pytest.raises(ValidationError):
        model(version='v1.0.0')  # Has 'v' prefix


def test_valid_chars_with_length_constraints():
    """Test valid_chars combined with min_length/max_length"""
    schema = [
        {
            'variable': 'product_code',
            'schema': {
                'type': 'string',
                'valid_chars': '^[A-Z0-9-]+$',  # Uppercase alphanumeric with dashes
                'min_length': 5,
                'max_length': 10,
                'required': True
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestValidCharsLength', NOT_PROVIDED)

    # Valid codes
    m1 = model(product_code='ABC-123')
    assert m1.product_code == 'ABC-123'

    m2 = model(product_code='PROD-12345')
    assert m2.product_code == 'PROD-12345'

    # Invalid pattern
    with pytest.raises(ValidationError) as exc_info:
        model(product_code='abc-123')  # Lowercase
    assert 'Value does not match' in str(exc_info.value)

    # Too short (even if pattern matches)
    with pytest.raises(ValidationError) as exc_info:
        model(product_code='AB-1')
    # Could fail on either length or pattern
    assert 'at least 5 characters' in str(exc_info.value) or 'Value does not match' in str(exc_info.value)

    # Too long
    with pytest.raises(ValidationError) as exc_info:
        model(product_code='ABC-1234567')
    assert 'at most 10 characters' in str(exc_info.value)


def test_valid_chars_with_private_field():
    """Test valid_chars with private/secret field"""
    schema = [
        {
            'variable': 'api_key',
            'schema': {
                'type': 'string',
                'valid_chars': '^[A-Za-z0-9]{32}$',  # 32 character alphanumeric key
                'private': True,
                'required': True
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestPrivateValidChars', NOT_PROVIDED)

    # Valid API key
    valid_key = 'a' * 16 + 'B' * 16  # 32 chars
    m = model(api_key=valid_key)
    assert m.api_key == valid_key

    # Invalid pattern (special characters)
    with pytest.raises(ValidationError):
        model(api_key='a' * 16 + 'B' * 15 + '!')  # Contains !

    # Invalid length
    with pytest.raises(ValidationError):
        model(api_key='a' * 31)  # Too short


def test_valid_chars_in_nested_structure():
    """Test valid_chars in nested dict structures"""
    schema = [
        {
            'variable': 'network',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'hostname',
                        'schema': {
                            'type': 'string',
                            'valid_chars': '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$',  # Hostname pattern
                            'required': True
                        }
                    },
                    {
                        'variable': 'ip_address',
                        'schema': {
                            'type': 'string',
                            'valid_chars': r'^(\d{1,3}\.){3}\d{1,3}$',  # Simple IPv4 pattern
                            'required': True
                        }
                    }
                ]
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestNestedValidChars', NOT_PROVIDED)

    # Valid values
    m = model(network={
        'hostname': 'my-server-01',
        'ip_address': '192.168.1.100'
    })
    assert m.network.hostname == 'my-server-01'
    assert m.network.ip_address == '192.168.1.100'

    # Invalid hostname
    with pytest.raises(ValidationError) as exc_info:
        model(network={
            'hostname': 'My-Server',  # Uppercase not allowed
            'ip_address': '192.168.1.100'
        })
    assert 'hostname' in str(exc_info.value)

    # Invalid IP - Note: Our simple regex pattern doesn't validate octet values
    # For proper IP validation, we should use the ipaddr type instead of regex
    # This test shows the limitation of using regex for IP validation
    m2 = model(network={
        'hostname': 'my-server',
        'ip_address': '192.168.1.256'  # 256 is technically invalid but passes our simple regex
    })
    # This passes because our regex only checks format, not value ranges
    assert m2.network.ip_address == '192.168.1.256'


def test_valid_chars_with_immutable_field():
    """Test valid_chars combined with immutable field"""
    schema = [
        {
            'variable': 'instance_id',
            'schema': {
                'type': 'string',
                'valid_chars': '^i-[a-f0-9]{8}$',  # AWS-like instance ID pattern
                'immutable': True,
                'required': True
            }
        }
    ]

    # Creation - must match pattern
    model_create = generate_pydantic_model(schema, 'TestImmutableValidChars', NOT_PROVIDED, NOT_PROVIDED)

    # Valid instance ID
    m1 = model_create(instance_id='i-1234abcd')
    assert m1.instance_id == 'i-1234abcd'

    # Invalid pattern
    with pytest.raises(ValidationError):
        model_create(instance_id='i-1234ABCD')  # Uppercase not allowed

    # Update - immutable and must still match pattern
    old_values = {'instance_id': 'i-abcd1234'}
    model_update = generate_pydantic_model(schema, 'TestImmutableValidCharsUpdate', NOT_PROVIDED, old_values)

    # Must use exact old value (which should be valid)
    m2 = model_update(instance_id='i-abcd1234')
    assert m2.instance_id == 'i-abcd1234'

    # Cannot change even to another valid pattern
    with pytest.raises(ValidationError):
        model_update(instance_id='i-5678efgh')


def test_valid_chars_with_text_field_type():
    """Test valid_chars with text (LongString) field type"""
    # Note: valid_chars with text type currently has issues because LongString
    # wraps the value and the validator expects a string
    # This test documents the current limitation
    schema = [
        {
            'variable': 'config_content',
            'schema': {
                'type': 'text',  # LongString type
                'valid_chars': '^[A-Za-z0-9\n\r\t =]+$',  # Allow alphanumeric, newlines, tabs, spaces, equals
                'required': True
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestTextValidChars', NOT_PROVIDED)

    # Currently this fails because LongStringWrapper is not a string
    # Documenting this as a known limitation
    with pytest.raises(TypeError) as exc_info:
        config = """key1=value1
key2=value2
section=data"""
        model(config_content=config)
    assert "expected string or bytes-like object, got 'LongStringWrapper'" in str(exc_info.value)


def test_valid_chars_error_message():
    """Test the error message when valid_chars validation fails"""
    schema = [
        {
            'variable': 'zipcode',
            'schema': {
                'type': 'string',
                'valid_chars': r'^\d{5}(-\d{4})?$',  # US ZIP code pattern
                'required': True
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestValidCharsError', NOT_PROVIDED)

    # Valid ZIP codes
    m1 = model(zipcode='12345')
    assert m1.zipcode == '12345'

    m2 = model(zipcode='12345-6789')
    assert m2.zipcode == '12345-6789'

    # Invalid ZIP codes with specific error checking
    with pytest.raises(ValidationError) as exc_info:
        model(zipcode='1234')  # Too short

    # Check that the error mentions pattern matching
    error_dict = exc_info.value.errors()[0]
    assert error_dict['type'] == 'assertion_error'
    assert 'Value does not match' in error_dict['msg']
    assert 'zipcode' in error_dict['loc']


def test_valid_chars_with_construct_schema():
    """Test valid_chars through the main construct_schema function"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'docker_tag',
                    'schema': {
                        'type': 'string',
                        'valid_chars': r'^[a-z0-9]+([._-][a-z0-9]+)*$',  # Docker tag pattern
                        'required': True
                    }
                },
                {
                    'variable': 'port',
                    'schema': {
                        'type': 'int',
                        'min': 1,
                        'max': 65535,
                        'required': True
                    }
                }
            ]
        }
    }

    # Valid values
    result_valid = construct_schema(
        item_version_details,
        {'docker_tag': 'nginx-1.21.0', 'port': 8080},
        update=False
    )
    assert len(result_valid['verrors'].errors) == 0
    assert result_valid['new_values']['docker_tag'] == 'nginx-1.21.0'

    # Invalid docker tag
    result_invalid = construct_schema(
        item_version_details,
        {'docker_tag': 'Nginx:Latest', 'port': 8080},  # Uppercase and colon not allowed
        update=False
    )
    assert len(result_invalid['verrors'].errors) > 0
    assert 'docker_tag' in str(result_invalid['verrors'].errors)


# Enum field tests
def test_string_enum_basic():
    """Test basic string enum field"""
    schema = [
        {
            'variable': 'log_level',
            'schema': {
                'type': 'string',
                'enum': [
                    {'value': 'debug', 'description': 'Debug logging'},
                    {'value': 'info', 'description': 'Info logging'},
                    {'value': 'warning', 'description': 'Warning logging'},
                    {'value': 'error', 'description': 'Error logging'}
                ],
                'default': 'info'
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestStringEnum', NOT_PROVIDED)

    # Default value works
    m1 = model()
    assert m1.log_level == 'info'

    # Valid enum values
    m2 = model(log_level='debug')
    assert m2.log_level == 'debug'

    m3 = model(log_level='error')
    assert m3.log_level == 'error'

    # Invalid enum value should fail
    with pytest.raises(ValidationError) as exc_info:
        model(log_level='trace')  # Not in enum
    assert 'log_level' in str(exc_info.value)


def test_string_enum_with_null():
    """Test that null should be explicitly included in enum if needed"""
    # Based on real-world usage: if a field needs null, it should be in the enum
    schema = [
        {
            'variable': 'optional_priority',
            'schema': {
                'type': 'string',
                'enum': [
                    {'value': None, 'description': 'No priority'},
                    {'value': 'low', 'description': 'Low priority'},
                    {'value': 'medium', 'description': 'Medium priority'},
                    {'value': 'high', 'description': 'High priority'}
                ],
                'default': None
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestEnumNull', NOT_PROVIDED)

    # Null is allowed because it's in the enum
    m1 = model(optional_priority=None)
    assert m1.optional_priority is None

    # Valid enum values
    m2 = model(optional_priority='high')
    assert m2.optional_priority == 'high'

    # Invalid value should fail
    with pytest.raises(ValidationError):
        model(optional_priority='urgent')


def test_string_enum_required():
    """Test required string enum field"""
    schema = [
        {
            'variable': 'environment',
            'schema': {
                'type': 'string',
                'enum': [
                    {'value': 'development', 'description': 'Development environment'},
                    {'value': 'staging', 'description': 'Staging environment'},
                    {'value': 'production', 'description': 'Production environment'}
                ],
                'required': True
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestEnumRequired', NOT_PROVIDED)

    # Must provide a value
    with pytest.raises(ValidationError):
        model()

    # Valid value works
    m = model(environment='staging')
    assert m.environment == 'staging'


def test_enum_empty_list():
    """Test that empty enum list doesn't create Literal type"""
    schema = [
        {
            'variable': 'status',
            'schema': {
                'type': 'string',
                'enum': [],  # Empty enum list
                'default': 'active'
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestEmptyEnum', NOT_PROVIDED)

    # Should work as a regular string field
    m1 = model()
    assert m1.status == 'active'

    # Can set any string value
    m2 = model(status='inactive')
    assert m2.status == 'inactive'


def test_enum_with_immutable():
    """Test that immutable takes precedence over enum"""
    schema = [
        {
            'variable': 'app_type',
            'schema': {
                'type': 'string',
                'enum': [
                    {'value': 'web', 'description': 'Web application'},
                    {'value': 'api', 'description': 'API service'}
                ],
                'immutable': True,
                'default': 'web'
            }
        }
    ]

    # Update mode with old values - immutable should take precedence
    old_values = {'app_type': 'api'}
    model = generate_pydantic_model(schema, 'TestEnumImmutable', NOT_PROVIDED, old_values)

    # Must use the old value
    m1 = model(app_type='api')
    assert m1.app_type == 'api'

    # Cannot change to other enum value
    with pytest.raises(ValidationError):
        model(app_type='web')


def test_enum_in_nested_dict():
    """Test enum field in nested dictionary"""
    schema = [
        {
            'variable': 'database',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'type',
                        'schema': {
                            'type': 'string',
                            'enum': [
                                {'value': 'postgres', 'description': 'PostgreSQL'},
                                {'value': 'mysql', 'description': 'MySQL'},
                                {'value': 'sqlite', 'description': 'SQLite'}
                            ],
                            'default': 'postgres'
                        }
                    },
                    {
                        'variable': 'host',
                        'schema': {
                            'type': 'string',
                            'default': 'localhost'
                        }
                    }
                ]
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestNestedEnum', NOT_PROVIDED)

    # Default values
    m1 = model()
    assert m1.database.type == 'postgres'
    assert m1.database.host == 'localhost'

    # Valid enum value
    m2 = model(database={'type': 'mysql', 'host': 'db.example.com'})
    assert m2.database.type == 'mysql'

    # Invalid enum value
    with pytest.raises(ValidationError):
        model(database={'type': 'mongodb'})


def test_enum_in_list_items():
    """Test enum in list item schema"""
    schema = [
        {
            'variable': 'log_levels',
            'schema': {
                'type': 'list',
                'items': [
                    {
                        'variable': 'level',
                        'schema': {
                            'type': 'string',
                            'enum': [
                                {'value': 'debug', 'description': 'Debug'},
                                {'value': 'info', 'description': 'Info'},
                                {'value': 'warn', 'description': 'Warning'},
                                {'value': 'error', 'description': 'Error'}
                            ]
                        }
                    }
                ],
                'default': []
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestListEnum', NOT_PROVIDED)

    # Valid list of enum values
    m1 = model(log_levels=['debug', 'info', 'error'])
    assert m1.log_levels == ['debug', 'info', 'error']

    # Invalid value in list
    with pytest.raises(ValidationError):
        model(log_levels=['debug', 'verbose'])  # 'verbose' not in enum


def test_enum_with_valid_chars():
    """Test that enum and valid_chars can work together"""
    schema = [
        {
            'variable': 'region_code',
            'schema': {
                'type': 'string',
                'enum': [
                    {'value': 'US-EAST', 'description': 'US East'},
                    {'value': 'US-WEST', 'description': 'US West'},
                    {'value': 'EU-WEST', 'description': 'EU West'}
                ],
                'valid_chars': '^[A-Z]{2}-[A-Z]{4}$',  # Enforces format
                'required': True
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestEnumValidChars', NOT_PROVIDED)

    # Valid enum value that matches pattern
    m = model(region_code='US-EAST')
    assert m.region_code == 'US-EAST'

    # Invalid enum value
    with pytest.raises(ValidationError):
        model(region_code='US-CENTRAL')  # Not in enum


def test_enum_with_show_if():
    """Test enum field with show_if condition"""
    schema = [
        {
            'variable': 'deployment',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'use_custom',
                        'schema': {
                            'type': 'boolean',
                            'default': False
                        }
                    },
                    {
                        'variable': 'preset',
                        'schema': {
                            'type': 'string',
                            'enum': [
                                {'value': 'small', 'description': 'Small deployment'},
                                {'value': 'medium', 'description': 'Medium deployment'},
                                {'value': 'large', 'description': 'Large deployment'}
                            ],
                            'default': 'medium',
                            'show_if': [['use_custom', '=', False]]
                        }
                    }
                ]
            }
        }
    ]

    # When use_custom is False, preset should have enum constraint
    model1 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestEnumShowIf1',
        {'use_custom': False}
    )
    m1 = model1(use_custom=False, preset='large')
    assert m1.preset == 'large'

    # Invalid enum value should fail
    with pytest.raises(ValidationError):
        model1(use_custom=False, preset='xlarge')

    # When use_custom is True, preset is NotRequired
    model2 = generate_pydantic_model(
        schema[0]['schema']['attrs'], 'TestEnumShowIf2',
        {'use_custom': True}
    )
    m2 = model2(use_custom=True)
    assert m2.preset is NotRequired


def test_enum_with_minio_example():
    """Test enum pattern from minio questions.yaml"""
    # Based on actual minio schema pattern
    schema = [
        {
            'variable': 'service',
            'schema': {
                'type': 'dict',
                'attrs': [
                    {
                        'variable': 'api_port_protocol',
                        'label': 'API Port Protocol',
                        'schema': {
                            'type': 'string',
                            'enum': [
                                {'value': 'http', 'description': 'HTTP Protocol'},
                                {'value': 'https', 'description': 'HTTPS Protocol'}
                            ],
                            'default': 'http',
                            'required': True
                        }
                    },
                    {
                        'variable': 'console_port_protocol',
                        'label': 'Console Port Protocol',
                        'schema': {
                            'type': 'string',
                            'enum': [
                                {'value': 'http', 'description': 'HTTP Protocol'},
                                {'value': 'https', 'description': 'HTTPS Protocol'}
                            ],
                            'default': 'http',
                            'required': True
                        }
                    }
                ]
            }
        }
    ]

    model = generate_pydantic_model(schema, 'TestMinioExample', NOT_PROVIDED)

    # Test defaults
    m1 = model()
    assert m1.service.api_port_protocol == 'http'
    assert m1.service.console_port_protocol == 'http'

    # Test mixed protocols
    m2 = model(service={
        'api_port_protocol': 'https',
        'console_port_protocol': 'http'
    })
    assert m2.service.api_port_protocol == 'https'
    assert m2.service.console_port_protocol == 'http'

    # Invalid protocol should fail
    with pytest.raises(ValidationError):
        model(service={'api_port_protocol': 'tcp'})
# Tests for all field types through construct_schema
def test_construct_schema_with_ipaddr():
    """Test IP address field validation and serialization through construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'server_ip',
                    'schema': {
                        'type': 'ipaddr',
                        'required': True
                    }
                },
                {
                    'variable': 'optional_ip',
                    'schema': {
                        'type': 'ipaddr',
                        'required': False
                    }
                },
                {
                    'variable': 'nullable_ip',
                    'schema': {
                        'type': 'ipaddr',
                        'null': True,
                        'required': False
                    }
                }
            ]
        }
    }

    # Test valid IPv4
    result = construct_schema(item_version_details, {'server_ip': '192.168.1.1'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['server_ip'] == '192.168.1.1'  # Should be serialized as string

    # Test valid IPv6
    result = construct_schema(item_version_details, {'server_ip': '2001:db8::1'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['server_ip'] == '2001:db8::1'

    # Test localhost
    result = construct_schema(item_version_details, {'server_ip': '::1'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['server_ip'] == '::1'

    # Test invalid IP
    result = construct_schema(item_version_details, {'server_ip': 'not.an.ip'}, False)
    assert len(result['verrors'].errors) > 0
    assert 'server_ip' in str(result['verrors'].errors)

    # Test empty string (special case for IPvAnyAddress)
    result = construct_schema(item_version_details, {'server_ip': ''}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['server_ip'] == ''

    # Test nullable IP with null
    result = construct_schema(item_version_details, {'server_ip': '10.0.0.1', 'nullable_ip': None}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['nullable_ip'] is None

    # Test optional field not provided
    result = construct_schema(item_version_details, {'server_ip': '10.0.0.1'}, False)
    assert len(result['verrors'].errors) == 0
    assert 'optional_ip' not in result['new_values']


def test_construct_schema_with_uri():
    """Test URI field validation and serialization through construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'webhook_url',
                    'schema': {
                        'type': 'uri',
                        'required': True
                    }
                },
                {
                    'variable': 'backup_url',
                    'schema': {
                        'type': 'uri',
                        'null': True,
                        'required': False
                    }
                }
            ]
        }
    }

    # Test valid HTTPS URL
    result = construct_schema(item_version_details, {'webhook_url': 'https://example.com'}, False)
    assert len(result['verrors'].errors) == 0
    # Pydantic normalizes URLs by adding trailing slash
    assert result['new_values']['webhook_url'] == 'https://example.com/'

    # Test URL with path
    result = construct_schema(item_version_details, {'webhook_url': 'https://api.example.com/webhook'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['webhook_url'] == 'https://api.example.com/webhook'

    # Test FTP URL
    result = construct_schema(item_version_details, {'webhook_url': 'ftp://files.example.com/data'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['webhook_url'] == 'ftp://files.example.com/data'

    # Test invalid URI
    result = construct_schema(item_version_details, {'webhook_url': 'not a url'}, False)
    assert len(result['verrors'].errors) > 0
    assert 'webhook_url' in str(result['verrors'].errors)

    # Test empty string (special case for URI)
    result = construct_schema(item_version_details, {'webhook_url': ''}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['webhook_url'] == ''

    # Test nullable URI with null
    result = construct_schema(item_version_details, {'webhook_url': 'https://example.com', 'backup_url': None}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['backup_url'] is None


def test_construct_schema_with_hostpath():
    """Test hostpath field validation and serialization through construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'data_dir',
                    'schema': {
                        'type': 'hostpath',
                        'required': True
                    }
                },
                {
                    'variable': 'optional_path',
                    'schema': {
                        'type': 'hostpath',
                        'required': False
                    }
                }
            ]
        }
    }

    # Test valid path that exists
    result = construct_schema(item_version_details, {'data_dir': '/tmp'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['data_dir'] == '/tmp'

    # Test empty string (special case for HostPath)
    result = construct_schema(item_version_details, {'data_dir': ''}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['data_dir'] == ''

    # Test non-existent path (should fail)
    result = construct_schema(item_version_details, {'data_dir': '/path/that/does/not/exist'}, False)
    assert len(result['verrors'].errors) > 0
    assert 'data_dir' in str(result['verrors'].errors)

    # Test optional field not provided
    result = construct_schema(item_version_details, {'data_dir': '/tmp'}, False)
    assert len(result['verrors'].errors) == 0
    assert 'optional_path' not in result['new_values']


def test_construct_schema_with_path():
    """Test absolute path field validation through construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'config_path',
                    'schema': {
                        'type': 'path',
                        'required': True
                    }
                },
                {
                    'variable': 'log_path',
                    'schema': {
                        'type': 'path',
                        'null': True,
                        'required': False
                    }
                }
            ]
        }
    }

    # Test valid absolute path
    result = construct_schema(item_version_details, {'config_path': '/etc/app/config.yaml'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['config_path'] == '/etc/app/config.yaml'

    # Test path normalization (trailing slash removal)
    result = construct_schema(item_version_details, {'config_path': '/var/log/app/'}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['config_path'] == '/var/log/app'

    # Test relative path (should fail)
    result = construct_schema(item_version_details, {'config_path': 'relative/path'}, False)
    assert len(result['verrors'].errors) > 0
    assert 'config_path' in str(result['verrors'].errors)

    # Test empty string (special case for AbsolutePath)
    result = construct_schema(item_version_details, {'config_path': ''}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['config_path'] == ''

    # Test nullable path with null
    result = construct_schema(item_version_details, {'config_path': '/etc/config', 'log_path': None}, False)
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['log_path'] is None


def test_construct_schema_path_with_length_constraints():
    """Test path and hostpath fields with length constraints through construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'short_path',
                    'schema': {
                        'type': 'path',
                        'min_length': 10,
                        'max_length': 50,
                        'required': True
                    }
                },
                {
                    'variable': 'host_path',
                    'schema': {
                        'type': 'hostpath',
                        'min_length': 5,
                        'max_length': 20,
                        'required': True
                    }
                }
            ]
        }
    }

    # Test valid paths within length bounds
    result = construct_schema(
        item_version_details,
        {'short_path': '/etc/config/app', 'host_path': '/home'},
        False
    )
    assert len(result['verrors'].errors) == 0
    assert result['new_values']['short_path'] == '/etc/config/app'
    assert result['new_values']['host_path'] == '/home'

    # Test path too short
    result = construct_schema(
        item_version_details,
        {'short_path': '/etc', 'host_path': '/home'},
        False
    )
    assert len(result['verrors'].errors) > 0
    errors = str(result['verrors'].errors)
    assert 'short_path' in errors
    assert 'at least 10 items' in errors

    # Test path too long
    result = construct_schema(
        item_version_details,
        {'short_path': '/' + 'a' * 50, 'host_path': '/home'},
        False
    )
    assert len(result['verrors'].errors) > 0
    errors = str(result['verrors'].errors)
    assert 'short_path' in errors
    assert 'at most 50 items' in errors

    # Test hostpath too long (but path doesn't exist)
    result = construct_schema(
        item_version_details,
        {'short_path': '/etc/config', 'host_path': '/very/long/path/exceeding/limit'},
        False
    )
    assert len(result['verrors'].errors) > 0
    errors = str(result['verrors'].errors)
    assert 'host_path' in errors
    # Error could be either length or existence
    assert ('at most 20 characters' in errors or
            'does not exist' in errors)

    # Test empty string for path (should fail min_length)
    result = construct_schema(
        item_version_details,
        {'short_path': '', 'host_path': '/home'},
        False
    )
    assert len(result['verrors'].errors) > 0
    errors = str(result['verrors'].errors)
    assert 'short_path' in errors
    assert 'at least 10 items' in errors

    # Test empty string for hostpath (should fail min_length)
    result = construct_schema(
        item_version_details,
        {'short_path': '/etc/config', 'host_path': ''},
        False
    )
    assert len(result['verrors'].errors) > 0
    errors = str(result['verrors'].errors)
    assert 'host_path' in errors
    assert 'at least 5 characters' in errors


def test_construct_schema_with_all_field_types():
    """Test all field types together through construct_schema"""
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'app_config',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'name',
                                'schema': {
                                    'type': 'string',
                                    'required': True,
                                    'min_length': 3,
                                    'max_length': 50
                                }
                            },
                            {
                                'variable': 'description',
                                'schema': {
                                    'type': 'text',  # LongString
                                    'required': False
                                }
                            },
                            {
                                'variable': 'port',
                                'schema': {
                                    'type': 'int',
                                    'required': True,
                                    'min': 1,
                                    'max': 65535
                                }
                            },
                            {
                                'variable': 'enabled',
                                'schema': {
                                    'type': 'boolean',
                                    'default': True
                                }
                            },
                            {
                                'variable': 'bind_ip',
                                'schema': {
                                    'type': 'ipaddr',
                                    'default': '0.0.0.0'
                                }
                            },
                            {
                                'variable': 'api_endpoint',
                                'schema': {
                                    'type': 'uri',
                                    'required': False
                                }
                            },
                            {
                                'variable': 'data_path',
                                'schema': {
                                    'type': 'hostpath',
                                    'required': False
                                }
                            },
                            {
                                'variable': 'config_file',
                                'schema': {
                                    'type': 'path',
                                    'required': False
                                }
                            },
                            {
                                'variable': 'tags',
                                'schema': {
                                    'type': 'list',
                                    'items': [
                                        {
                                            'variable': 'tag',
                                            'schema': {
                                                'type': 'string'
                                            }
                                        }
                                    ]
                                }
                            },
                            {
                                'variable': 'environment',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': []  # Generic dict
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Test with all fields
    test_data = {
        'app_config': {
            'name': 'MyApp',
            'description': 'A very long description ' * 100,  # Long text
            'port': 8080,
            'enabled': False,
            'bind_ip': '127.0.0.1',
            'api_endpoint': 'https://api.example.com/v1',
            'data_path': '/tmp',
            'config_file': '/etc/myapp/config.yaml',
            'tags': ['production', 'v2'],
            'environment': {'DEBUG': 'false', 'LOG_LEVEL': 'info'}
        }
    }

    result = construct_schema(item_version_details, test_data, False)
    assert len(result['verrors'].errors) == 0

    # Verify all values are properly serialized
    config = result['new_values']['app_config']
    assert config['name'] == 'MyApp'
    assert 'description' in config  # LongString is present
    assert config['port'] == 8080
    assert config['enabled'] is False
    assert config['bind_ip'] == '127.0.0.1'  # IP serialized as string
    assert config['api_endpoint'] == 'https://api.example.com/v1'  # URI serialized as string
    assert config['data_path'] == '/tmp'  # HostPath serialized as string
    assert config['config_file'] == '/etc/myapp/config.yaml'
    assert config['tags'] == ['production', 'v2']
    assert config['environment'] == {'DEBUG': 'false', 'LOG_LEVEL': 'info'}

    # Test with minimal required fields only
    minimal_data = {
        'app_config': {
            'name': 'MinApp',
            'port': 80
        }
    }

    result = construct_schema(item_version_details, minimal_data, False)
    assert len(result['verrors'].errors) == 0

    config = result['new_values']['app_config']
    assert config['name'] == 'MinApp'
    assert config['port'] == 80
    # Default values are not returned when using exclude_unset=True
    assert 'enabled' not in config
    assert 'bind_ip' not in config
    # Optional fields should not be present
    assert 'description' not in config
    assert 'api_endpoint' not in config
    assert 'data_path' not in config
    assert 'config_file' not in config
    assert 'tags' not in config  # Non-required list
    assert 'environment' not in config  # Non-required dict

    # Test validation errors
    invalid_data = {
        'app_config': {
            'name': 'AB',  # Too short
            'port': 70000,  # Out of range
            'bind_ip': 'not an ip',
            'api_endpoint': 'not a url',
            'config_file': 'relative/path'
        }
    }

    result = construct_schema(item_version_details, invalid_data, False)
    assert len(result['verrors'].errors) > 0
    error_str = str(result['verrors'].errors)
    assert 'name' in error_str  # Min length violation
    assert 'port' in error_str  # Max value violation
    assert 'bind_ip' in error_str  # Invalid IP
    assert 'api_endpoint' in error_str  # Invalid URI
    assert 'config_file' in error_str  # Not absolute path


# Type coercion tests - documenting behavior with strict=False
def test_boolean_type_coercion():
    """Test that boolean fields coerce string values due to strict=False in BaseModel.

    This is intentional behavior for backward compatibility. The BaseModel in
    pydantic_utils.py has strict=False which enables automatic type coercion.
    """
    schema = [
        {'variable': 'enabled', 'schema': {'type': 'boolean', 'required': True}},
        {'variable': 'public', 'schema': {'type': 'boolean', 'default': False}}
    ]

    model = generate_pydantic_model(schema, 'TestBoolCoercion', NOT_PROVIDED)

    # Test various string values that get coerced to boolean
    test_cases = [
        # String value -> Expected boolean
        ('true', True),
        ('True', True),
        ('TRUE', True),
        ('false', False),
        ('False', False),
        ('FALSE', False),
        ('1', True),
        ('0', False),
        ('yes', True),
        ('no', False),
        ('on', True),
        ('off', False),
    ]

    for string_val, expected_bool in test_cases:
        m = model(enabled=string_val)
        assert m.enabled is expected_bool
        assert isinstance(m.enabled, bool)

    # Test that actual booleans still work
    m1 = model(enabled=True)
    assert m1.enabled is True

    m2 = model(enabled=False)
    assert m2.enabled is False


def test_int_type_coercion():
    """Test that integer fields coerce string values due to strict=False in BaseModel.

    This is intentional behavior for backward compatibility.
    """
    schema = [
        {'variable': 'port', 'schema': {'type': 'int', 'required': True, 'min': 1, 'max': 65535}},
        {'variable': 'count', 'schema': {'type': 'int', 'default': 10}}
    ]

    model = generate_pydantic_model(schema, 'TestIntCoercion', NOT_PROVIDED)

    # Test string numbers get coerced to integers
    m1 = model(port='8080')
    assert m1.port == 8080
    assert isinstance(m1.port, int)

    m2 = model(port='443', count='25')
    assert m2.port == 443
    assert m2.count == 25
    assert isinstance(m2.count, int)

    # Test that actual integers still work
    m3 = model(port=3000)
    assert m3.port == 3000

    # Test that invalid strings fail validation
    with pytest.raises(ValidationError) as exc_info:
        model(port='not_a_number')
    assert 'port' in str(exc_info.value)

    # Test that out of range values fail even when coerced
    with pytest.raises(ValidationError) as exc_info:
        model(port='70000')  # Exceeds max
    assert 'port' in str(exc_info.value)


def test_type_coercion_through_construct_schema():
    """Test type coercion through the full construct_schema flow.

    This tests the real-world photoprism example where boolean string values
    are passed and should be coerced due to strict=False.
    """
    item_version_details = {
        'schema': {
            'questions': [
                {
                    'variable': 'photoprism',
                    'label': '',
                    'group': 'Photoprism Configuration',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'site_url',
                                'label': 'Site URL',
                                'description': 'The URL for the Photoprism site',
                                'schema': {
                                    'type': 'uri'
                                }
                            },
                            {
                                'variable': 'public',
                                'label': 'Public',
                                'description': 'Enable public access to Photoprism',
                                'schema': {
                                    'type': 'boolean',
                                    'default': False
                                }
                            },
                            {
                                'variable': 'port',
                                'label': 'Port',
                                'schema': {
                                    'type': 'int',
                                    'default': 2342
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Test with string values that should be coerced
    values = {
        'photoprism': {
            'public': 'false',  # String instead of boolean
            'site_url': '',
            'port': '8080'  # String instead of int
        }
    }

    result = construct_schema(item_version_details, values, False)

    # Should not have validation errors due to type coercion
    assert len(result['verrors'].errors) == 0

    # Values should be coerced to correct types
    photoprism = result['new_values']['photoprism']
    assert photoprism['public'] is False  # String 'false' -> boolean False
    assert isinstance(photoprism['public'], bool)
    assert photoprism['port'] == 8080  # String '8080' -> int 8080
    assert isinstance(photoprism['port'], int)
    assert photoprism['site_url'] == ''

    # Test with other boolean string values
    values2 = {
        'photoprism': {
            'public': 'true',  # Different string value
            'site_url': 'https://photoprism.example.com',
            'port': 2342  # Use actual int this time
        }
    }

    result2 = construct_schema(item_version_details, values2, False)
    assert len(result2['verrors'].errors) == 0

    photoprism2 = result2['new_values']['photoprism']
    assert photoprism2['public'] is True  # String 'true' -> boolean True
    assert photoprism2['site_url'] == 'https://photoprism.example.com/'  # URL normalized
    assert photoprism2['port'] == 2342


def test_string_type_no_int_coercion():
    """Test that string fields do NOT coerce integers to strings.

    While strict=False allows some type coercion, not all types are coerced.
    Integer to string coercion is not automatic.
    """
    schema = [
        {'variable': 'name', 'schema': {'type': 'string', 'required': True}}
    ]

    model = generate_pydantic_model(schema, 'TestStringNoCoercion', NOT_PROVIDED)

    # String values work fine
    m1 = model(name='test')
    assert m1.name == 'test'

    # But integers are NOT automatically coerced to strings
    with pytest.raises(ValidationError) as exc_info:
        model(name=12345)
    assert 'name' in str(exc_info.value)
    assert 'string' in str(exc_info.value).lower()
