import pytest
from mock import Mock

from middlewared.service_exception import ValidationErrors
from middlewared.schema import (
    accepts, Bool, Cron, Dict, Dir, Error, File, Float, Int, IPAddr, List, Str, UnixPerm,
)


def test__schema_str_empty():

    @accepts(Str('data', empty=False))
    def strempty(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        strempty(self, '')


def test__schema_str_non_empty():

    @accepts(Str('data', empty=True))
    def strempty(self, data):
        return data

    self = Mock()

    assert strempty(self, '') == ''


def test__schema_str_null():

    @accepts(Str('data', null=True))
    def strnull(self, data):
        return data

    self = Mock()

    assert strnull(self, None) is None


def test__schema_str_not_null():

    @accepts(Str('data', null=False))
    def strnotnull(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        assert strnotnull(self, None) is not None


@pytest.mark.parametrize("value,expected", [
    ('foo', 'foo'),
    (3, '3'),
    (False, Error),
    (3.3, Error),
    (["foo"], Error),
])
def test__schema_str_values(value, expected):

    @accepts(Str('data'))
    def strv(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error) as ei:
            strv(self, value)
        assert ei.value.errmsg == 'Not a string'
    else:
        assert strv(self, value) == expected


@pytest.mark.parametrize("value,expected", [
    ('FOO', 'FOO'),
    ('BAR', 'BAR'),
    ('FOOBAR', Error),
])
def test__schema_str_num(value, expected):

    @accepts(Str('data', enum=['FOO', 'BAR']))
    def strv(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error) as ei:
            strv(self, value)
        assert ei.value.errmsg.startswith('Invalid choice')
    else:
        assert strv(self, value) == expected


def test__schema_bool_null():

    @accepts(Bool('data', null=True))
    def boolnull(self, data):
        return data

    self = Mock()

    assert boolnull(self, None) is None


def test__schema_bool_not_null():

    @accepts(Bool('data', null=False))
    def boolnotnull(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        assert boolnotnull(self, None) is not None


def test__schema_float_null():

    @accepts(Float('data', null=True))
    def floatnull(self, data):
        return data

    self = Mock()

    assert floatnull(self, None) is None


def test__schema_float_not_null():

    @accepts(Float('data', null=False))
    def floatnotnull(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        assert floatnotnull(self, None) is not None


@pytest.mark.parametrize("value,expected", [
    (5, 5.0),
    ('5', 5.0),
    ('5.0', 5.0),
    (5.0, 5.0),
    ('FOO', Error),
    (False, Error),
    ([4], Error),
])
def test__schema_float_values(value, expected):

    @accepts(Float('data', null=False))
    def floatv(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error) as ei:
            floatv(self, value)
        assert ei.value.errmsg == 'Not a floating point number'
    else:
        assert floatv(self, value) == expected


def test__schema_int_null():

    @accepts(Int('data', null=True))
    def intnull(self, data):
        return data

    self = Mock()

    assert intnull(self, None) is None


def test__schema_int_not_null():

    @accepts(Int('data', null=False))
    def intnotnull(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        assert intnotnull(self, None) is not None


@pytest.mark.parametrize("value,expected", [
    (3, 3),
    ('3', 3),
    (3.0, Error),
    ('FOO', Error),
    (False, Error),
    ([4], Error),
])
def test__schema_int_values(value, expected):

    @accepts(Int('data'))
    def intv(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error) as ei:
            intv(self, False)
        assert ei.value.errmsg == 'Not an integer'
    else:
        assert intv(self, value) == expected


def test__schema_dict_null():

    @accepts(Dict('data', null=True))
    def dictnull(self, data):
        return data

    self = Mock()

    assert dictnull(self, None) == {}


def test__schema_dict_not_null():

    @accepts(Str('data', null=False))
    def dictnotnull(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        assert dictnotnull(self, None) != {}


@pytest.mark.parametrize("value,expected", [
    ({'foo': 'foo'}, {'foo': 'foo'}),
    ({}, {}),
    ({'foo': None}, Error),
    ({'bar': None}, Error),
])
def test__schema_dict_not_null_args(value, expected):

    @accepts(Dict(
        'data',
        Str('foo'),
        Bool('bar'),
    ))
    def dictargs(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error) as ei:
            dictargs(self, value)
        assert ei.value.errmsg == 'null not allowed'
    else:
        assert dictargs(self, value) == expected


@pytest.mark.parametrize("value,expected", [
    ({'foo': 'foo', 'bar': False, 'list': []}, {'foo': 'foo', 'bar': False, 'list': []}),
    ({'foo': 'foo'}, Error),
    ({'bar': False}, Error),
    ({'foo': 'foo', 'bar': False}, Error),
])
def test__schema_dict_required_args(value, expected):

    @accepts(Dict(
        'data',
        Str('foo', required=True),
        Bool('bar', required=True),
        List('list', required=True),
    ))
    def dictargs(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error) as ei:
            dictargs(self, value)
        assert ei.value.errmsg == 'attribute required'
    else:
        assert dictargs(self, value) == expected


@pytest.mark.parametrize("value,expected,msg", [
    ({'foo': 'foo', 'bar': False}, {'foo': 'foo', 'bar': False}, None),
    ({'foo': 'foo', 'bar': False, 'num': 5}, {'foo': 'foo', 'bar': False, 'num': 5}, None),
    ({'foo': 'foo'}, {'foo': 'foo'}, None),
    ({'foo': 'foo', 'list': ['listitem']}, {'foo': 'foo', 'list': ['listitem']}, None),
    ({'foo': 'foo', 'list': 5}, Error, 'Not a list'),
    ({'foo': 'foo', 'bar': False, 'num': None}, Error, 'null not allowed'),
    ({'foo': None}, Error, 'null not allowed'),
    ({'bar': None}, Error, 'attribute required'),
])
def test__schema_dict_mixed_args(value, expected, msg):

    @accepts(Dict(
        'data',
        Str('foo', required=True),
        Bool('bar', null=True),
        Int('num'),
        List('list', items=[Str('listitem')]),
    ))
    def dictargs(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error) as ei:
            dictargs(self, value)
        assert ei.value.errmsg == msg
    else:
        assert dictargs(self, value) == expected


def test__schema_list_empty():

    @accepts(List('data', empty=False))
    def listempty(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        listempty(self, [])


def test__schema_list_non_empty():

    @accepts(List('data', empty=True))
    def listempty(self, data):
        return data

    self = Mock()

    assert listempty(self, []) == []


def test__schema_list_null():

    @accepts(List('data', null=True))
    def listnull(self, data):
        return data

    self = Mock()

    assert listnull(self, None) == None


def test__schema_list_not_null():

    @accepts(List('data', null=False))
    def listnotnull(self, data):
        return data

    self = Mock()

    with pytest.raises(Error):
        assert listnotnull(self, None) != []


def test__schema_list_noarg_not_null():

    @accepts(List('data', null=False))
    def listnotnull(self, data):
        return data

    self = Mock()

    with pytest.raises(Error) as ei:
        listnotnull(self)
    assert ei.value.errmsg == 'attribute required'


@pytest.mark.parametrize("value,expected", [
    (["foo"], ["foo"]),
    ([2], ["2"]),
    ([2, "foo"], ["2", "foo"]),
    ([False], Error),
    ("foo", Error),
    ({"foo": "bar"}, Error),
])
def test__schema_list_items(value, expected):

    @accepts(List('data', items=[Str('foo')]))
    def listnotnull(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error):
            listnotnull(self, [False])
    else:
        assert listnotnull(self, value) == expected


def test__schema_unixperm_null():

    @accepts(UnixPerm('data', null=True))
    def unixpermnull(self, data):
        return data

    self = Mock()

    assert unixpermnull(self, None) is None


def test__schema_dir_null():

    @accepts(Dir('data', null=True))
    def dirnull(self, data):
        return data

    self = Mock()

    assert dirnull(self, None) is None


def test__schema_file_null():

    @accepts(File('data', null=True))
    def filenull(self, data):
        return data

    self = Mock()

    assert filenull(self, None) is None


@pytest.mark.parametrize("value,expected", [
    ({'minute': '55'}, {'minute': '55'}),
    ({'dow': '2'}, {'dow': '2'}),
    ({'hour': '*'}, {'hour': '*'}),
    ({'minute': '66'}, Error),
    ({'hour': '-25'}, Error),
    ({'dom': '33'}, Error),
])
def test__schema_cron_values(value, expected):

    @accepts(Cron('data'))
    def cronv(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(ValidationErrors):
            cronv(self, value)
    else:
        assert cronv(self, value) == expected


@pytest.mark.parametrize("value,expected", [
    ('127.0.0.1', '127.0.0.1'),
    ('22::56', '22::56'),
    ('192.', ValidationErrors),
    ('5:5', ValidationErrors),
    ('ff:ff:ee:aa', ValidationErrors),
])
def test__schema_ipaddr(value, expected):

    @accepts(IPAddr('data'))
    def ipaddrv(self, data):
        return data

    self = Mock()

    if expected is ValidationErrors:
        with pytest.raises(ValidationErrors):
            ipaddrv(self, value)
    else:
        assert ipaddrv(self, value) == expected


@pytest.mark.parametrize("value,expected", [
    ('127.0.0.1/32', '127.0.0.1/32'),
    ('22::56', '22::56'),
    ('192.', ValidationErrors),
    ('5:5', ValidationErrors),
    ('ff:ff:ee:aa', ValidationErrors),
    ('192.168.3.1/33', ValidationErrors),
    ('ff::4/129', ValidationErrors),
])
def test__schema_ipaddr_cidr(value, expected):

    @accepts(IPAddr('data', cidr=True))
    def ipaddrv(self, data):
        return data

    self = Mock()

    if expected is ValidationErrors:
        with pytest.raises(ValidationErrors):
            ipaddrv(self, value)
    else:
        assert ipaddrv(self, value) == expected
