import operator
import re
from collections.abc import Container
from types import MappingProxyType


def op_in(x: object, y: Container[object]) -> bool:
    return operator.contains(y, x)


def op_rin(x: Container[object] | None, y: object) -> bool:
    if x is None:
        return False
    return operator.contains(x, y)


def op_nin(x: object, y: Container[object]) -> bool:
    if x is None:
        return False
    return not operator.contains(y, x)


def op_rnin(x: Container[object] | None, y: object) -> bool:
    if x is None:
        return False
    return not operator.contains(x, y)


def op_re(x: str | None, y: str) -> bool:
    # Some string fields are nullable. If this is the case then we will treat the null as an empty string
    # so that the regex match doesn't raise an exception.
    return re.match(y, x or '') is not None


def op_startswith(x: str | None, y: str) -> bool:
    if x is None:
        return False
    return x.startswith(y)


def op_notstartswith(x: str | None, y: str) -> bool:
    if x is None:
        return False
    return not x.startswith(y)


def op_endswith(x: str | None, y: str) -> bool:
    if x is None:
        return False
    return x.endswith(y)


def op_notendswith(x: str | None, y: str) -> bool:
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
