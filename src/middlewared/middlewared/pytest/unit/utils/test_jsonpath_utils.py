import pytest

from middlewared.utils import jsonpath


# =============================================================================
# Tests for dot_notation_to_json_path()
# =============================================================================

@pytest.mark.parametrize('dot_notation,expected', [
    # Basic dot notation (existing behavior)
    ('foo.bar', '$.foo.bar'),  # we're getting subkey and so should be JSONPath
    ('foobar', 'foobar'),  # does not require JSONPath and so should stay same
    ('foo.bar.stuff', '$.foo.bar.stuff'),

    # Array index bracket notation - NEW
    ('foo.bar[0]', '$.foo.bar[0]'),  # array index at end
    ('foo.bar[0].baz', '$.foo.bar[0].baz'),  # array index in middle
    ('foo[0].bar', '$.foo[0].bar'),  # array index after first segment
    ('event_data.params[0].username', '$.event_data.params[0].username'),  # audit use case
    ('event_data.params[0]', '$.event_data.params[0]'),  # array index at end, no further nesting
    ('foo.bar[10].baz[2].qux', '$.foo.bar[10].baz[2].qux'),  # multiple array indexes
])
def test_dot_notation_conversion(dot_notation, expected):
    assert jsonpath.dot_notation_to_json_path(dot_notation) == expected


# =============================================================================
# Tests for query_filters_json_path_parse() - Audit plugin filter conversion
# =============================================================================

@pytest.mark.parametrize('filters_in,filters_out', [
    # Basic filters (existing behavior)
    ([['foo.bar', '=', 'canary']], [['$.foo.bar', '=', 'canary']]),
    ([['foo', '=', 'canary']], [['foo', '=', 'canary']]),
    (
        [["OR", [[['foo', '=', 'canary']], [['foo.bar', '=', 'canary']]]]],
        [["OR", [[['foo', '=', 'canary']], [['$.foo.bar', '=', 'canary']]]]],
    ),

    # Array index bracket notation in filters - NEW
    (
        [['event_data.params[0].username', '=', 'barney']],
        [['$.event_data.params[0].username', '=', 'barney']]
    ),
    (
        [['event_data.method', '=', 'user.create'], ['event_data.params[0].username', '=', 'barney']],
        [['$.event_data.method', '=', 'user.create'], ['$.event_data.params[0].username', '=', 'barney']]
    ),
    # Array index in OR filters
    (
        [["OR", [[['event_data.params[0].id', '=', 1]], [['event_data.params[0].id', '=', 2]]]]],
        [["OR", [[['$.event_data.params[0].id', '=', 1]], [['$.event_data.params[0].id', '=', 2]]]]]
    ),
    # Multiple array indexes
    (
        [['data.items[0].values[1]', '=', 'test']],
        [['$.data.items[0].values[1]', '=', 'test']]
    ),
])
def test_filters_json_path_parse(filters_in, filters_out):
    assert jsonpath.query_filters_json_path_parse(filters_in) == filters_out


# =============================================================================
# Tests for json_path_parse() - Datastore column/path splitting
# =============================================================================

@pytest.mark.parametrize('json_path,expected', [
    # Basic nested paths (existing behavior)
    ('$.foo.bar', ('foo', '$.bar')),
    ('$.foo.bar.tar', ('foo', '$.bar.tar')),

    # Array index in nested path
    ('$.event_data.params[0]', ('event_data', '$.params[0]')),
    ('$.event_data.params[0].username', ('event_data', '$.params[0].username')),
    ('$.foo.bar[0].baz', ('foo', '$.bar[0].baz')),
    ('$.foo.items[0].values[1]', ('foo', '$.items[0].values[1]')),

    # Top-level array index (no dot after column)
    ('$.roles[0]', ('roles', '$[0]')),
    ('$.params[0]', ('params', '$[0]')),

    # Single column (no nested path)
    ('$.roles', ('roles', '$')),
])
def test_json_path_parse(json_path, expected):
    assert jsonpath.json_path_parse(json_path) == expected
