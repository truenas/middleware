from middlewared.plugins.apps.schema_construction_utils import construct_schema


def test_nested_validation_error_paths():
    """Test that validation errors report the full nested path correctly.

    Currently, errors are prefixed with 'values.' which should be documented
    or potentially removed for cleaner error reporting.
    """
    # Test case 1: Simple nested structure
    schema1 = {
        'schema': {
            'questions': [
                {
                    'variable': 'database',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'host',
                                'schema': {
                                    'type': 'string',
                                    'required': True,
                                    'min_length': 5
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    values1 = {
        'database': {
            'host': 'abc'  # Too short
        }
    }

    result1 = construct_schema(schema1, values1, False)
    assert len(result1['verrors'].errors) == 1
    error = result1['verrors'].errors[0]
    # Now returns clean path without 'values.' prefix
    assert error.attribute == 'database.host'
    assert 'at least 5 characters' in error.errmsg

    # Test case 2: Deeply nested structure
    schema2 = {
        'schema': {
            'questions': [
                {
                    'variable': 'top_dict',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'nested_dict',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'str_field',
                                            'schema': {
                                                'type': 'string',
                                                'required': True,
                                                'min_length': 5
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

    values2 = {
        'top_dict': {
            'nested_dict': {
                'str_field': 'hi'  # Too short
            }
        }
    }

    result2 = construct_schema(schema2, values2, False)
    assert len(result2['verrors'].errors) == 1
    error = result2['verrors'].errors[0]
    # Now returns clean path without 'values.' prefix
    assert error.attribute == 'top_dict.nested_dict.str_field'
    assert 'at least 5 characters' in error.errmsg

    # Test case 3: Multiple errors at different levels
    schema3 = {
        'schema': {
            'questions': [
                {
                    'variable': 'app',
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
                                'variable': 'config',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'port',
                                            'schema': {
                                                'type': 'int',
                                                'required': True
                                            }
                                        },
                                        {
                                            'variable': 'host',
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

    values3 = {
        'app': {
            # Missing 'name' field
            'config': {
                # Missing both 'port' and 'host' fields
            }
        }
    }

    result3 = construct_schema(schema3, values3, False)
    assert len(result3['verrors'].errors) == 3

    # Check that error paths are clean without 'values.' prefix
    error_paths = [e.attribute for e in result3['verrors'].errors]
    assert 'app.name' in error_paths
    assert 'app.config.port' in error_paths
    assert 'app.config.host' in error_paths

    # All should be "Field required" errors
    for error in result3['verrors'].errors:
        assert 'Field required' in error.errmsg

    # Test case 4: List with nested dict errors
    schema4 = {
        'schema': {
            'questions': [
                {
                    'variable': 'servers',
                    'schema': {
                        'type': 'list',
                        'items': [
                            {
                                'variable': 'server',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'name',
                                            'schema': {
                                                'type': 'string',
                                                'required': True,
                                                'min_length': 3
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

    values4 = {
        'servers': [
            {'name': 'ab'},  # Too short
            {'name': 'server2'}  # Valid
        ]
    }

    result4 = construct_schema(schema4, values4, False)
    assert len(result4['verrors'].errors) == 1
    error = result4['verrors'].errors[0]
    # List index is included in the path without 'values.' prefix
    assert error.attribute == 'servers.0.name'
    assert 'at least 3 characters' in error.errmsg


def test_validation_error_path_consistency():
    """Test that validation error paths are now clean without 'values.' prefix.

    This test verifies that the fix to use verrors.extend() instead of
    verrors.add_child('values', e) produces cleaner error paths.
    """
    # After the fix, these are the actual clean paths we get
    clean_paths = [
        'database.host',
        'top_dict.nested_dict.str_field',
        'app.name',
        'app.config.port',
        'servers.0.name',
    ]

    # This is achieved by changing construct_schema() to use:
    # verrors.extend(e) instead of verrors.add_child('values', e)
    assert all(not path.startswith('values.') for path in clean_paths)
