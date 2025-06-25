from middlewared.plugins.apps.schema_construction_utils import construct_schema


def test_nested_show_if_parent_hides_children():
    """Test that when a parent dict field is hidden by show_if, its required children don't cause validation errors.

    This tests the specific case from actual-budget where:
    - storage.data.type = 'ix_volume' (default)
    - storage.data.host_path_config has show_if: [['type', '=', 'host_path']]
    - storage.data.host_path_config.path is required

    When type is 'ix_volume', host_path_config should be hidden and its required path field shouldn't validate.
    """
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'storage',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'data',
                                'schema': {
                                    'type': 'dict',
                                    'attrs': [
                                        {
                                            'variable': 'type',
                                            'schema': {
                                                'type': 'string',
                                                'default': 'ix_volume',
                                                'required': True
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
                                                            'default': 'data',
                                                            'required': True
                                                        }
                                                    }
                                                ]
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

    # Test with ix_volume type (default) - host_path_config.path should NOT be required
    values = {
        'storage': {
            'data': {
                'type': 'ix_volume',
                'ix_volume_config': {
                    'dataset_name': 'data'
                }
                # Note: no host_path_config provided
            }
        }
    }

    result = construct_schema(schema, values, False)
    # Should not have validation errors
    assert len(result['verrors'].errors) == 0

    # Test with host_path type - host_path_config.path SHOULD be required
    values2 = {
        'storage': {
            'data': {
                'type': 'host_path',
                'host_path_config': {
                    # Missing required 'path' field
                }
            }
        }
    }

    result2 = construct_schema(schema, values2, False)
    # Should have validation error for missing path
    assert len(result2['verrors'].errors) == 1
    assert 'path' in result2['verrors'].errors[0].attribute


def test_nested_show_if_with_nested_conditions():
    """Test nested show_if with conditions at multiple levels."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'app',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'enable_feature',
                                'schema': {
                                    'type': 'boolean',
                                    'default': False,
                                    'required': True
                                }
                            },
                            {
                                'variable': 'feature_config',
                                'schema': {
                                    'type': 'dict',
                                    'show_if': [['enable_feature', '=', True]],
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
                                            'variable': 'advanced_config',
                                            'schema': {
                                                'type': 'dict',
                                                'show_if': [['mode', '=', 'advanced']],
                                                'attrs': [
                                                    {
                                                        'variable': 'required_setting',
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

    # Test with feature disabled - all nested fields should be optional
    values = {
        'app': {
            'enable_feature': False
            # No feature_config provided
        }
    }

    result = construct_schema(schema, values, False)
    assert len(result['verrors'].errors) == 0

    # Test with feature enabled but basic mode - advanced_config fields should be optional
    values2 = {
        'app': {
            'enable_feature': True,
            'feature_config': {
                'mode': 'basic'
                # No advanced_config provided
            }
        }
    }

    result2 = construct_schema(schema, values2, False)
    assert len(result2['verrors'].errors) == 0

    # Test with feature enabled and advanced mode - required_setting should be required
    values3 = {
        'app': {
            'enable_feature': True,
            'feature_config': {
                'mode': 'advanced',
                'advanced_config': {
                    # Missing required_setting
                }
            }
        }
    }

    result3 = construct_schema(schema, values3, False)
    assert len(result3['verrors'].errors) == 1
    assert 'required_setting' in result3['verrors'].errors[0].attribute


def test_show_if_preserves_existing_behavior():
    """Ensure our changes don't break existing show_if behavior."""
    schema = {
        'schema': {
            'questions': [
                {
                    'variable': 'network',
                    'schema': {
                        'type': 'dict',
                        'attrs': [
                            {
                                'variable': 'publish',
                                'schema': {
                                    'type': 'boolean',
                                    'default': False,
                                    'required': True
                                }
                            },
                            {
                                'variable': 'port',
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
        }
    }

    # When publish is False, port should not be required
    values = {'network': {'publish': False}}
    result = construct_schema(schema, values, False)
    assert len(result['verrors'].errors) == 0
    # The existing show_if logic should handle this

    # When publish is True, port should use default
    values2 = {'network': {'publish': True}}
    result2 = construct_schema(schema, values2, False)
    assert len(result2['verrors'].errors) == 0
    # The existing show_if logic should inject the default
