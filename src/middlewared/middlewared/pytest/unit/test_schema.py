import pytest
from mock import Mock

from middlewared.service import job
from middlewared.service_exception import ValidationErrors
from middlewared.schema import (
    accepts, Bool, Cron, Dict, Dir, Error, File, Float, Int, IPAddr, List, Str, UnixPerm,
)


def test__nonhidden_after_hidden():
    with pytest.raises(ValueError):
        @accepts(Int('id'), Bool('fake', hidden=True), List('flags'))
        def f(self, id, fake, flags):
            pass


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

    assert dictnull(self, None) == None


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


@pytest.mark.parametrize('items,value', [
    ([List('b', items=[List('c', private=True)])], [[['a']]]),
    ([Dict('b', Str('c', private=True))], [{'c': 'secret'}])
])
def test__schema_list_private_items(items, value):
    assert List('a', items=items).dump(value) == '********'


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
            listnotnull(self, value)
    else:
        assert listnotnull(self, value) == expected


@pytest.mark.parametrize('value,expected', [
    (['foo'], ['foo']),
    ([True, True, 'foo'], [True, True, 'foo']),
    ([2, {'bool': True}], ['2', {'bool': True}]),
    ([2, {'bool': True, 'str': False}], Error),
    ({'foo': False}, Error),
    ({'unexpected': False}, Error),
    ('foo', Error),
    ({'foo': 'foo'}, Error),
])
def test__schema_list_multiple_items(value, expected):

    @accepts(List('data', items=[Str('foo'), Bool('bool'), Dict('dict', Bool('bool'), Str('str'))]))
    def listnotnull(self, data):
        return data

    self = Mock()

    if expected is Error:
        with pytest.raises(Error):
            listnotnull(self, value)
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
        result = {k: v for k, v in cronv(self, value).items() if k in expected}
        assert result == expected


@pytest.mark.parametrize("data_dict,begin_end,result", [
    (
        {"cron_minute": "00", "cron_hour": "01", "cron_daymonth": "02", "cron_month": "03", "cron_dayweek": "04"},
        False,
        {"schedule": {"minute": "00", "hour": "01", "dom": "02", "month": "03", "dow": "04"}},
    ),
    (
        {"cron_minute": "00", "cron_hour": None, "cron_daymonth": "02", "cron_month": "03", "cron_dayweek": "04"},
        False,
        {"schedule": None},
    ),
    (
        {"cron_minute": "00", "cron_hour": "01", "cron_daymonth": "02", "cron_month": "03", "cron_dayweek": "04",
         "cron_begin": "05:00:00", "cron_end": "06:00:00"},
        True,
        {"schedule": {"minute": "00", "hour": "01", "dom": "02", "month": "03", "dow": "04",
                      "begin": "05:00", "end": "06:00"}},
    ),
    (
        {"cron_minute": "00", "cron_hour": None, "cron_daymonth": "02", "cron_month": "03", "cron_dayweek": "04",
         "cron_begin": "05:00:00", "cron_end": "06:00:00"},
        True,
        {"schedule": None},
    ),
    (
        {"cron_minute": "00", "cron_hour": "01", "cron_daymonth": "02", "cron_month": "03", "cron_dayweek": "04",
         "cron_begin": "05:00:00", "cron_end": None},
        True,
        {"schedule": None},
    ),
])
def test__cron__convert_db_format_to_schedule(data_dict, begin_end, result):
    Cron.convert_db_format_to_schedule(data_dict, "schedule", "cron_", begin_end)
    assert data_dict == result


@pytest.mark.parametrize("value,error", [
    ({'hour': '0', 'minute': '0', 'begin': '09:00', 'end': '18:00'}, True),
    ({'hour': '9', 'minute': '0', 'begin': '09:00', 'end': '18:00'}, False),
    ({'hour': '9', 'minute': '0', 'begin': '09:10', 'end': '18:00'}, True),
    ({'hour': '9', 'minute': '15', 'begin': '09:10', 'end': '18:00'}, False),
])
def test__cron__begin_end_validate(value, error):

    @accepts(Cron('data', begin_end=True))
    def cronv(self, data):
        return data

    self = Mock()

    if error:
        with pytest.raises(ValidationErrors):
            cronv(self, value)
    else:
        cronv(self, value)


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
    ('22::56/64', '22::56/64'),
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


def test__schema_str_default():

    @accepts(Str('foo'), Str('bar', default='BAR'))
    def strdef(self, foo, bar):
        return bar

    self = Mock()

    assert strdef(self, 'foo') == 'BAR'


def test__schema_str_job_default():
    """
    Job changes the order of the parameters in schema\
    """

    @accepts(Str('foo'), Str('bar', default='BAR'))
    @job()
    def strdef(self, job, foo, bar):
        return bar

    self = Mock()
    jobm = Mock()

    assert strdef(self, jobm, 'foo') == 'BAR'
