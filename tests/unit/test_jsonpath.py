import pytest
from middlewared.utils import jsonpath


@pytest.mark.parametrize('dot_notation,expected', [
    ('foo.bar', '$.foo.bar'),  # we're getting subkey and so should be JSONPath
    ('foobar', 'foobar'),  # does not require JSONPath and so should stay same
    ('foo.bar.stuff', '$.foo.bar.stuff')
])
def test_dot_notation_conversion(dot_notation, expected):
    assert jsonpath.dot_notation_to_json_path(dot_notation) == expected


@pytest.mark.parametrize('filters_in,filters_out', [
    ([['foo.bar', '=', 'canary']], [['$.foo.bar', '=', 'canary']]),
    ([['foo', '=', 'canary']], [['foo', '=', 'canary']]),
    (
        [['foo', '=', 'canary'], ['foo.bar', '=', 'canary']],
        [['foo', '=', 'canary'], ['$.foo.bar', '=', 'canary']],
    ),
    (
        [["OR", [['foo', '=', 'canary'], ['foo.bar', '=', 'canary']]]],
        [["OR", [['foo', '=', 'canary'], ['$.foo.bar', '=', 'canary']]]],
    ),
    (
        [["OR", [['foo', '=', 'canary'], ['foo.bar', '=', 'canary'], ['foo.bar', '=', 'finch']]]],
        [["OR", [['foo', '=', 'canary'], ['$.foo.bar', '=', 'canary'], ['$.foo.bar', '=', 'finch']]]],
    ),
    (
        [
            ['pk', '=', 'primary_key'],
            ["OR", [['foo', '=', 'canary'], ['foo.bar', '=', 'canary'], ['foo.bar', '=', 'finch']]]
        ],
        [
            ['pk', '=', 'primary_key'],
            ["OR", [['foo', '=', 'canary'], ['$.foo.bar', '=', 'canary'], ['$.foo.bar', '=', 'finch']]]
        ],
    ),
])
def test_filters_json_path_parse(filters_in, filters_out):
    assert jsonpath.query_filters_json_path_parse(filters_in) == filters_out


@pytest.mark.parametrize('filters_in', [
    ([["OR", [['foo', '=', 'canary']], [['foo', '=', 'finch']]]])
])
def test_filters_json_path_parse_failures(filters_in):
    with pytest.raises(ValueError, match='invalid filter format'):
        jsonpath.query_filters_json_path_parse(filters_in)


@pytest.mark.parametrize('json_path,expected', [
    ('$.foo.bar', ('foo', '$.bar')),
    ('$.foo.bar.tar', ('foo', '$.bar.tar')),
])
def test_json_path_parse(json_path, expected):
    assert jsonpath.json_path_parse(json_path) == expected
