import yaml

from middlewared.plugins.apps.ix_apps.utils import QuotedStrDumper


def test_basic_string_quoting():
    """Test that basic strings are properly quoted."""
    data = {'key': 'value'}
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    assert result == '"key": "value"\n'


def test_numeric_strings_quoted():
    """Test that numeric-looking strings are quoted."""
    data = {
        'numeric': '12345',
        'float': '3.14',
        'hex': '0xFF',
        'octal': '0o755',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    assert '"12345"' in result
    assert '"3.14"' in result
    assert '"0xFF"' in result
    assert '"0o755"' in result


def test_boolean_strings_quoted():
    """Test that boolean-looking strings are quoted."""
    data = {
        'true_str': 'true',
        'false_str': 'false',
        'yes_str': 'yes',
        'no_str': 'no',
        'on_str': 'on',
        'off_str': 'off',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    assert '"true"' in result
    assert '"false"' in result
    assert '"yes"' in result
    assert '"no"' in result
    assert '"on"' in result
    assert '"off"' in result


def test_scientific_notation_strings():
    """Test that scientific notation strings are quoted to prevent misinterpretation."""
    # These strings can be interpreted as numbers in scientific notation if not quoted
    data = {
        'scientific1': '8E1',  # Would become 80.0
        'scientific2': '1e3',  # Would become 1000.0
        'scientific3': '2.5e-2',  # Would become 0.025
        'scientific4': '8E1',  # The problematic case from docker-compose
        'minus_sign': '-m',  # Could be interpreted as negative
        'plus_sign': '+5',  # Could be interpreted as positive number
        'inf_string': '.inf',  # YAML infinity
        'neg_inf': '-.inf',  # Negative infinity
        'nan_string': '.nan',  # Not a number
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)

    # All should be quoted to preserve string type
    assert '"8E1"' in result
    assert '"1e3"' in result
    assert '"2.5e-2"' in result
    assert '"-m"' in result
    assert '"+5"' in result
    assert '".inf"' in result
    assert '"-.inf"' in result
    assert '".nan"' in result

    # Verify round-trip preserves strings, not converted to numbers
    loaded = yaml.safe_load(result)
    assert loaded == data
    assert loaded['scientific1'] == '8E1'  # Must remain string, not 80.0
    assert isinstance(loaded['scientific1'], str)
    assert loaded['scientific2'] == '1e3'  # Must remain string, not 1000.0
    assert isinstance(loaded['scientific2'], str)


def test_docker_compose_case():
    """Test the specific docker-compose case with command arguments."""
    # This mimics the docker-compose.yaml structure
    data = {
        'services': {
            'test': {
                'command': ['-m', '8E1'],
                'entrypoint': ['/my/entrypoint'],
                'image': 'my/image:latest'
            }
        }
    }

    result = yaml.dump(data, Dumper=QuotedStrDumper)

    # The problematic '8E1' should be quoted
    assert '- "-m"' in result or '"-m"' in result
    assert '- "8E1"' in result or '"8E1"' in result

    # Verify round-trip preserves the exact strings
    loaded = yaml.safe_load(result)
    assert loaded == data
    assert loaded['services']['test']['command'][1] == '8E1'
    assert isinstance(loaded['services']['test']['command'][1], str)
    # Ensure it didn't become 80.0
    assert loaded['services']['test']['command'][1] != 80.0


def test_special_yaml_strings_quoted():
    """Test that YAML special strings are quoted."""
    data = {
        'null_str': 'null',
        'none_str': 'None',
        'tilde': '~',
        'empty': '',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    assert '"null"' in result
    assert '"None"' in result
    assert '"~"' in result
    assert '""' in result


def test_strings_with_special_characters():
    """Test strings containing special characters."""
    data = {
        'colon': 'key: value',
        'dash': '- item',
        'hash': '# comment',
        'bracket': '[array]',
        'brace': '{dict}',
        'pipe': '| block',
        'gt': '> fold',
        'asterisk': '*reference',
        'ampersand': '&anchor',
        'exclamation': '!tag',
        'percent': '%directive',
        'at': '@symbol',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # All should be quoted
    for value in data.values():
        assert f'"{value}"' in result


def test_strings_with_quotes():
    """Test strings containing various quote characters."""
    data = {
        'single': "it's",
        'double': 'say "hello"',
        'both': '''it's "fine"''',
        'escaped_single': "it\\'s",  # noqa: LIT102,LIT013
        'escaped_double': 'say \\"hello\\"',  # noqa: LIT102
        'backtick': '`command`',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Should handle quotes properly
    assert yaml.safe_load(result) == data


def test_strings_with_whitespace():
    """Test strings with various whitespace characters."""
    data = {
        'space': 'hello world',
        'leading_space': '  indented',
        'trailing_space': 'trailing  ',
        'tab': 'tab\there',
        'mixed': '  \t mixed \t  ',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # All should be quoted
    assert '"hello world"' in result
    assert '"  indented"' in result
    assert '"trailing  "' in result
    # Verify round-trip
    assert yaml.safe_load(result) == data


def test_multiline_strings_block_style():
    """Test that multiline strings use block literal style."""
    data = {
        'multiline': 'line1\nline2\nline3',
        'with_blank': 'line1\n\nline3',
        'trailing_newline': 'line1\nline2\n',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Should use block literal style (|-)
    assert '|-' in result
    # Verify round-trip
    loaded = yaml.safe_load(result)
    assert loaded == data


def test_strings_with_escape_sequences():
    """Test strings with various escape sequences."""
    data = {
        'newline': 'before\nafter',
        'carriage': 'before\rafter',
        'tab': 'before\tafter',
        'backslash': 'path\\to\\file',  # noqa: LIT102
        'null_char': 'null\0char',
        'unicode': 'emoji 😀',
        'form_feed': 'page\fbreak',
        'vertical_tab': 'vertical\vtab',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Multiline should use block style
    assert '|-' in result
    # Verify round-trip preserves all characters
    loaded = yaml.safe_load(result)
    assert loaded == data


def test_path_strings():
    """Test filesystem path strings."""
    data = {
        'unix_path': '/usr/local/bin',
        'unix_home': '~/documents',
        'windows_path': 'C:\\Program Files\\App',  # noqa: LIT102
        'unc_path': '\\\\server\\share',  # noqa: LIT102
        'relative': '../parent/child',
        'current': './current',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # All should be quoted
    for key in data:
        assert f'"{key}"' in result
    # Verify round-trip
    assert yaml.safe_load(result) == data


def test_url_strings():
    """Test URL strings."""
    data = {
        'http': 'http://example.com',
        'https': 'https://secure.example.com',
        'ftp': 'ftp://files.example.com',
        'file': 'file:///path/to/file',
        'with_port': 'http://localhost:8080',
        'with_query': 'https://api.example.com?key=value&foo=bar',
        'with_fragment': 'https://docs.example.com#section',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # All should be quoted
    for value in data.values():
        assert f'"{value}"' in result or value in result
    # Verify round-trip
    assert yaml.safe_load(result) == data


def test_command_strings():
    """Test command line strings."""
    data = {
        'simple_cmd': 'ls -la',
        'pipe': 'cat file | grep pattern',
        'redirect': 'echo "test" > output.txt',
        'background': 'long_process &',
        'multiple': 'cmd1 && cmd2 || cmd3',
        'subshell': '$(echo test)',
        'variable': '$HOME/bin',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Verify round-trip
    assert yaml.safe_load(result) == data


def test_json_like_strings():
    """Test JSON-like strings."""
    data = {
        'json_obj': '{"key": "value"}',
        'json_arr': '["item1", "item2"]',
        'nested': '{"outer": {"inner": "value"}}',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Should be properly quoted
    # Verify round-trip
    assert yaml.safe_load(result) == data


def test_non_string_types():
    """Test that non-string types are handled correctly."""
    data = {
        'integer': 42,
        'float': 3.14,
        'boolean_true': True,
        'boolean_false': False,
        'null_value': None,
        'list': [1, 2, 3],
        'dict': {'nested': 'value'},
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Strings should be quoted, others should not
    assert '"integer"' in result
    assert ': 42' in result
    assert '"float"' in result
    assert ': 3.14' in result
    assert '"boolean_true"' in result
    assert ': true' in result
    assert '"boolean_false"' in result
    assert ': false' in result
    assert '"null_value"' in result
    assert ': null' in result
    # Verify round-trip
    assert yaml.safe_load(result) == data


def test_nested_structures():
    """Test nested data structures."""
    data = {
        'config': {
            'app_name': 'test-app',
            'version': '1.0.0',
            'settings': {
                'debug': True,
                'port': 8080,
                'hosts': ['localhost', '0.0.0.0'],
            },
            'environment': {
                'PATH': '/usr/bin:/usr/local/bin',
                'HOME': '/home/user',
            },
        }
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # All string keys and values should be quoted
    assert '"config"' in result
    assert '"app_name"' in result
    assert '"test-app"' in result
    assert '"version"' in result
    assert '"1.0.0"' in result
    # Verify round-trip
    assert yaml.safe_load(result) == data


def test_list_of_strings():
    """Test lists containing various strings."""
    data = {
        'items': [
            'simple',
            '123',
            'true',
            'null',
            '',
            'with spaces',
            'special: chars',
            'multi\nline',
        ]
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # List items should be quoted
    assert '- "simple"' in result
    assert '- "123"' in result
    assert '- "true"' in result
    assert '- "null"' in result
    assert '- ""' in result
    assert '- "with spaces"' in result
    # Verify round-trip
    loaded = yaml.safe_load(result)
    assert loaded == data


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    data = {
        'very_long': 'x' * 1000,  # Long string
        'unicode_emoji': '🎉🎊🎈🎁🎀',
        'mixed_unicode': 'Hello 世界 مرحبا мир',
        'zero_width': 'zero\u200bwidth',
        'control_chars': 'bell\x07char',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Verify round-trip
    loaded = yaml.safe_load(result)
    assert loaded == data


def test_yaml_anchors_and_aliases():
    """Test that YAML anchors and aliases work correctly."""
    shared_config = {'host': 'localhost', 'port': 8080}
    data = {
        'primary': shared_config,
        'secondary': shared_config,  # Should create an alias
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    # Verify round-trip preserves structure
    loaded = yaml.safe_load(result)
    assert loaded == data
    # Verify that modifications to one affect the other (alias behavior)
    loaded['primary']['port'] = 9090
    assert loaded['secondary']['port'] == 9090


def test_compatibility_with_safe_load():
    """Test that output can be parsed with yaml.safe_load."""
    test_cases = [
        {'simple': 'string'},
        {'number': 42},
        {'boolean': True},
        {'null': None},
        {'list': [1, 'two', True, None]},
        {'nested': {'deep': {'structure': 'value'}}},
        {'multiline': 'line1\nline2\nline3'},
        {'special': 'key: value'},
    ]

    for data in test_cases:
        dumped = yaml.dump(data, Dumper=QuotedStrDumper)
        loaded = yaml.safe_load(dumped)
        assert loaded == data, f"Failed for: {data}"


def test_consistent_output():
    """Test that the same input always produces the same output."""
    data = {
        'key1': 'value1',
        'key2': 'value2',
        'nested': {'a': 1, 'b': 2},
    }
    output1 = yaml.dump(data, Dumper=QuotedStrDumper)
    output2 = yaml.dump(data, Dumper=QuotedStrDumper)
    assert output1 == output2


def test_empty_collections():
    """Test empty collections."""
    data = {
        'empty_dict': {},
        'empty_list': [],
        'empty_string': '',
    }
    result = yaml.dump(data, Dumper=QuotedStrDumper)
    assert '{}' in result
    assert '[]' in result
    assert '""' in result
    # Verify round-trip
    assert yaml.safe_load(result) == data
