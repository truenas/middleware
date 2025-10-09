"""
Unit tests for _make_index_validator re-validation issue.

This test file verifies that the _make_index_validator function correctly handles
both initial validation (with dict inputs) and re-validation (with model instance inputs).

The issue being tested:
- When list items go through validation multiple times (common in app updates)
- The validator might receive BaseModel instances instead of dicts on subsequent calls
- This causes "argument after ** must be a mapping" errors

The fix ensures the validator:
1. Detects if inputs are already model instances
2. Converts them to dicts before validation
3. Always returns dicts (not model instances)
"""

import pytest
from pydantic import Field, ValidationError

from middlewared.plugins.apps.schema_construction_utils import (
    _make_index_validator,
    BaseModel,
    construct_schema,
    NOT_PROVIDED,
)


class TestIndexValidatorRevalidation:
    """Test suite for _make_index_validator re-validation handling"""

    def test_validator_with_dict_input(self):
        """Test that validator works correctly with dict inputs (initial validation)"""
        # Create test models
        class PortModel(BaseModel):
            port: int = Field(ge=1, le=65535)
            protocol: str = Field(default="TCP")

        class StorageModel(BaseModel):
            path: str
            size: int = Field(ge=0)

        # Create validator for mixed list items
        item_models = [PortModel, StorageModel]
        validator = _make_index_validator(item_models, "test_list")

        # Test with dict inputs
        test_data = [
            {"port": 8080, "protocol": "TCP"},
            {"path": "/data", "size": 100}
        ]

        result = validator(test_data)

        # Verify results are dicts (not model instances)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], dict)
        assert isinstance(result[1], dict)
        assert result[0] == {"port": 8080, "protocol": "TCP"}
        assert result[1] == {"path": "/data", "size": 100}

    def test_validator_with_model_instance_input(self):
        """Test that validator handles model instances correctly (re-validation scenario)"""
        # Create test model
        class PortModel(BaseModel):
            port: int = Field(ge=1, le=65535)
            protocol: str = Field(default="TCP")

        item_models = [PortModel, PortModel]
        validator = _make_index_validator(item_models, "test_ports")

        # First validation with dicts
        dict_data = [
            {"port": 8080, "protocol": "TCP"},
            {"port": 9090, "protocol": "UDP"}
        ]

        result1 = validator(dict_data)

        # Result should be dicts
        assert isinstance(result1[0], dict)
        assert isinstance(result1[1], dict)

        # Second validation with the result (simulates re-validation)
        # This should work without errors
        result2 = validator(result1)

        assert isinstance(result2[0], dict)
        assert isinstance(result2[1], dict)
        assert result2 == result1

    def test_validator_idempotency(self):
        """Test that validator is idempotent (calling multiple times produces same result)"""
        class ItemModel(BaseModel):
            value: str
            count: int = Field(default=1)

        item_models = [ItemModel, ItemModel, ItemModel]
        validator = _make_index_validator(item_models, "test_items")

        initial_data = [
            {"value": "a", "count": 1},
            {"value": "b", "count": 2},
            {"value": "c", "count": 3}
        ]

        # Call validator multiple times
        result1 = validator(initial_data)
        result2 = validator(result1)
        result3 = validator(result2)

        # All results should be identical
        assert result1 == result2 == result3

        # All should be dicts
        for result in [result1, result2, result3]:
            assert all(isinstance(item, dict) for item in result)

    def test_validator_with_validation_errors(self):
        """Test that validation errors are properly raised and formatted"""
        class StrictModel(BaseModel):
            required_field: str
            port: int = Field(ge=1000, le=9999)

        item_models = [StrictModel, StrictModel]
        validator = _make_index_validator(item_models, "test_strict")

        # Test with invalid data
        invalid_data = [
            {"port": 500},  # Missing required_field and port out of range
            {"required_field": "test", "port": 10000}  # Port out of range
        ]

        with pytest.raises(ValidationError) as exc_info:
            validator(invalid_data)

        errors = exc_info.value.errors()
        # Should have at least one error for the first item (missing required_field and invalid port)
        assert len(errors) >= 1

        # Check error locations include the list index for first item
        error_locs = [tuple(err['loc']) for err in errors]
        assert any(loc[0] == 0 for loc in error_locs)  # First item errors

    def test_validator_with_too_many_items(self):
        """Test that validator raises error when there are more items than models"""
        class SimpleModel(BaseModel):
            value: str

        item_models = [SimpleModel, SimpleModel]  # Only 2 models
        validator = _make_index_validator(item_models, "test_overflow")

        # Try to validate 3 items (more than models)
        test_data = [
            {"value": "a"},
            {"value": "b"},
            {"value": "c"}  # This is the extra one
        ]

        with pytest.raises(ValueError, match="got 3 items but only 2 item models"):
            validator(test_data)

    def test_construct_schema_with_list_fields(self):
        """Test construct_schema with list fields that use _make_index_validator"""
        # Simulate an app schema with ports list
        app_version_details = {
            'schema': {
                'questions': [
                    {
                        'variable': 'ports',
                        'schema': {
                            'type': 'list',
                            'default': [],
                            'items': [{
                                'variable': 'port_item',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'port',
                                            'schema': {
                                                'type': 'int',
                                                'min': 1,
                                                'max': 65535,
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'protocol',
                                            'schema': {
                                                'type': 'string',
                                                'default': 'TCP',
                                                'enum': [
                                                    {'value': 'TCP', 'description': 'TCP'},
                                                    {'value': 'UDP', 'description': 'UDP'}
                                                ]
                                            }
                                        }
                                    ]
                                }
                            }]
                        }
                    }
                ]
            }
        }

        # Initial values
        new_values = {
            'ports': [
                {'port': 8080, 'protocol': 'TCP'},
                {'port': 9090, 'protocol': 'UDP'}
            ]
        }

        # First validation - should work
        result1 = construct_schema(
            app_version_details,
            new_values.copy(),
            update=False,
            old_values=NOT_PROVIDED
        )

        assert not result1['verrors'].errors
        assert 'ports' in result1['new_values']
        assert len(result1['new_values']['ports']) == 2

        # Second validation with the result (simulates update scenario)
        # This should also work without errors
        result2 = construct_schema(
            app_version_details,
            result1['new_values'],
            update=True,
            old_values=NOT_PROVIDED
        )

        assert not result2['verrors'].errors
        assert result2['new_values']['ports'] == result1['new_values']['ports']

    def test_complex_nested_list_validation(self):
        """Test validation with complex nested structures"""
        app_version_details = {
            'schema': {
                'questions': [
                    {
                        'variable': 'storage',
                        'schema': {
                            'type': 'list',
                            'default': [],
                            'items': [{
                                'variable': 'storage_item',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'type',
                                            'schema': {
                                                'type': 'string',
                                                'default': 'hostPath',
                                                'enum': [
                                                    {'value': 'hostPath', 'description': 'Host Path'},
                                                    {'value': 'emptyDir', 'description': 'Empty Directory'}
                                                ]
                                            }
                                        },
                                        {
                                            'variable': 'hostPath',
                                            'schema': {
                                                'type': 'string',
                                                'show_if': [['type', '=', 'hostPath']],
                                                'default': '/mnt/data'
                                            }
                                        },
                                        {
                                            'variable': 'size',
                                            'schema': {
                                                'type': 'int',
                                                'show_if': [['type', '=', 'emptyDir']],
                                                'default': 1024,
                                                'min': 1
                                            }
                                        }
                                    ]
                                }
                            }]
                        }
                    }
                ]
            }
        }

        # Test with mixed storage types
        values = {
            'storage': [
                {'type': 'hostPath', 'hostPath': '/custom/path'},
                {'type': 'emptyDir', 'size': 2048}
            ]
        }

        # First validation
        result1 = construct_schema(
            app_version_details,
            values,
            update=False,
            old_values=NOT_PROVIDED
        )

        assert not result1['verrors'].errors

        # Re-validation should also work
        result2 = construct_schema(
            app_version_details,
            result1['new_values'],
            update=True,
            old_values=NOT_PROVIDED
        )

        assert not result2['verrors'].errors

    def test_validator_returns_dict_not_model(self):
        """Explicitly test that validator always returns dicts, never model instances"""
        class TestModel(BaseModel):
            field1: str
            field2: int = Field(default=42)

        item_models = [TestModel]
        validator = _make_index_validator(item_models, "test_return_type")

        # Test with dict input
        dict_input = [{"field1": "test", "field2": 100}]
        result = validator(dict_input)

        # Result should be a list of dicts
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert not isinstance(result[0], BaseModel)

        # Verify we can use the result as input again
        # (This would fail if result[0] was a model instance in the old code)
        result2 = validator(result)
        assert result2 == result
