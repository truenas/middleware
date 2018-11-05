from middlewared.utils import filter_list


DATA = [
    {
        'foo': 'foo1',
        'number': 1,
        'list': [1],
    },
    {
        'foo': 'foo2',
        'number': 2,
        'list': [2],
    },
    {
        'foo': '_foo_',
        'number': 3,
        'list': [3],
    },
]


def test__filter_list_equal():
    assert len(filter_list(DATA, [['foo', '=', 'foo1']])) == 1


def test__filter_list_starts():
    assert len(filter_list(DATA, [['foo', '^', 'foo']])) == 2


def test__filter_list_ends():
    assert len(filter_list(DATA, [['foo', '$', '_']])) == 1


def test__filter_list_regex_begins():
    assert len(filter_list(DATA, [['foo', '~', '^foo']])) == 2


def test__filter_list_regex_contains():
    assert len(filter_list(DATA, [['foo', '~', '.*foo.*']])) == 3


def test__filter_list_gt():
    assert len(filter_list(DATA, [['number', '>', 1]])) == 2


def test__filter_list_gte():
    assert len(filter_list(DATA, [['number', '>=', 1]])) == 3


def test__filter_list_lt():
    assert len(filter_list(DATA, [['number', '<', 3]])) == 2


def test__filter_list_lte():
    assert len(filter_list(DATA, [['number', '<=', 3]])) == 3


def test__filter_list_in():
    assert len(filter_list(DATA, [['number', 'in', [1, 3]]])) == 2


def test__filter_list_nin():
    assert len(filter_list(DATA, [['number', 'nin', [1, 3]]])) == 1


def test__filter_list_rin():
    assert len(filter_list(DATA, [['list', 'rin', 1]])) == 1


def test__filter_list_rnin():
    assert len(filter_list(DATA, [['list', 'rnin', 1]])) == 2


def test__filter_list_OR_eq1():
    assert len(filter_list(DATA, [['OR', [
        ['number', '=', 1],
        ['number', '=', 200],
    ]]])) == 1


def test__filter_list_OR_eq2():
    assert len(filter_list(DATA, [['OR', [
        ['number', '=', 1],
        ['number', '=', 2],
    ]]])) == 2
