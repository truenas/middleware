import pytest

from middlewared.plugins.apps.schema_construction_utils import construct_schema


def test_construct_schema_simple_string():
    """Test construct_schema with a simple string field"""
    data = {
        'schema': {
            'questions': [
                {
                    'variable': 'app_name',
                    'label': 'Application Name',
                    'schema': {
                        'type': 'string',
                        'required': True
                    }
                }
            ]
        }
    }
    
    new_values = {'app_name': 'MyTestApp'}
    
    result = construct_schema(data, new_values, update=False)
    
    # Check that validation passed
    assert len(result['verrors'].errors) == 0
    
    # Check the schema name is correct
    assert result['schema_name'] == 'app_create'
    
    # Check that values are returned correctly
    assert result['new_values'] == new_values
    
    # Check that model was created
    assert result['model'] is not None
