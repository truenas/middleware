import operator
import re
from types import MappingProxyType


def op_in(x, y):
    return operator.contains(y, x)


def op_rin(x, y):
    if x is None:
        return False
    return operator.contains(x, y)


def op_nin(x, y):
    if x is None:
        return False
    return not operator.contains(y, x)


def op_rnin(x, y):
    if x is None:
        return False
    return not operator.contains(x, y)


def op_re(x, y):
    # Some string fields are nullable. If this is the case then we will treat the null as an empty string
    # so that the regex match doesn't raise an exception.
    return re.match(y, x or '')


def op_startswith(x, y):
    if x is None:
        return False
    return x.startswith(y)


def op_notstartswith(x, y):
    if x is None:
        return False
    return not x.startswith(y)


def op_endswith(x, y):
    if x is None:
        return False
    return x.endswith(y)


def op_notendswith(x, y):
    if x is None:
        return False
    return not x.endswith(y)


opmap = MappingProxyType({
    '=': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '>=': operator.ge,
    '<': operator.lt,
    '<=': operator.le,
    '~': op_re,
    'in': op_in,
    'nin': op_nin,
    'rin': op_rin,
    'rnin': op_rnin,
    '^': op_startswith,
    '!^': op_notstartswith,
    '$': op_endswith,
    '!$': op_notendswith,
})
