import asyncio
import errno
import functools
import logging
import operator
import re
import subprocess
import time
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, NamedTuple, overload, Protocol, Sequence, TypeVar

from middlewared.service_exception import MatchNotFound
from .lang import undefined
from .prctl import die_with_parent
from .threading import io_thread_pool_executor


# Define Product Strings
@dataclass(slots=True, frozen=True)
class ProductTypes:
    COMMUNITY_EDITION: str = 'COMMUNITY_EDITION'
    ENTERPRISE: str = 'ENTERPRISE'


@dataclass(slots=True, frozen=True)
class ProductNames:
    PRODUCT_NAME: str = 'TrueNAS'


ProductType = ProductTypes()
ProductName = ProductNames()

MID_PID = None
MIDDLEWARE_RUN_DIR = '/var/run/middleware'
MIDDLEWARE_BOOT_ENV_STATE_DIR = '/var/lib/truenas-middleware'
MIDDLEWARE_STARTED_SENTINEL_PATH = f'{MIDDLEWARE_RUN_DIR}/middlewared-started'
BOOTREADY = f'{MIDDLEWARE_RUN_DIR}/.bootready'
BOOT_POOL_NAME_VALID = ['freenas-boot', 'boot-pool']
MANIFEST_FILE = '/data/manifest.json'
BRAND = ProductName.PRODUCT_NAME
NULLS_FIRST = 'nulls_first:'
NULLS_LAST = 'nulls_last:'
REVERSE_CHAR = '-'
MAX_FILTERS_DEPTH = 3
TIMESTAMP_DESIGNATOR = '.$date'

logger = logging.getLogger(__name__)
_T = TypeVar('_T', str, list[str], None)
_V = TypeVar('_V')
_SelectList = Iterable[str | list[str]]
_Entry = dict[str, Any]


class UnexpectedFailure(Exception):
    pass


class FilterGetResult(NamedTuple):
    result: Any
    key: str | None = None
    done: bool = True


class GetterProtocol(Protocol):
    def __call__(self, obj: object, path: str) -> FilterGetResult: ...


def bisect(condition: Callable[[_V], Any], iterable: Iterable[_V]) -> tuple[list[_V], list[_V]]:
    a = []
    b = []
    for val in iterable:
        if condition(val):
            a.append(val)
        else:
            b.append(val)

    return a, b


def Popen(args, *, shell: bool = False, **kwargs):
    if shell:
        return asyncio.create_subprocess_shell(args, **kwargs)
    else:
        return asyncio.create_subprocess_exec(*args, **kwargs)


currently_running_subprocesses = set()


async def run(*args, **kwargs):
    if isinstance(args[0], list):
        args = tuple(args[0])

    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    kwargs.setdefault('check', True)
    if 'encoding' in kwargs:
        kwargs.setdefault('errors', 'strict')
    kwargs.setdefault('close_fds', True)
    kwargs['preexec_fn'] = die_with_parent

    loop = asyncio.get_event_loop()
    subprocess_identifier = f"{time.monotonic()}: {args!r}"
    try:
        currently_running_subprocesses.add(subprocess_identifier)
        try:
            return await loop.run_in_executor(
                io_thread_pool_executor,
                functools.partial(subprocess.run, args, **kwargs),
            )
        finally:
            currently_running_subprocesses.discard(subprocess_identifier)
    except OSError as e:
        if e.errno == errno.EMFILE:
            logger.warning("Currently running async subprocesses: %r", currently_running_subprocesses)

        raise


def partition(s: str) -> tuple[str, str]:
    rv = ''
    while True:
        left, sep, right = s.partition('.')
        if not sep:
            return rv + left, right
        if left[-1] == '\\':
            rv += left[:-1] + sep
            s = right
        else:
            return rv + left, right


def get_impl(obj: object, path: str) -> FilterGetResult:
    right = path
    cur = obj
    while right:
        left, right = partition(right)
        if isinstance(cur, dict):
            cur = cur.get(left, undefined)
        elif isinstance(cur, (list, tuple)):
            if not left.isdigit():
                # return all members and the remaining portion of path
                if left == '*':
                    return FilterGetResult(result=cur, key=right, done=False)

                raise ValueError(f'{left}: must be array index or wildcard character')

            left = int(left)
            cur = cur[left] if left < len(cur) else None

    return FilterGetResult(cur)


def get_attr(obj: object, path: str) -> FilterGetResult:
    """
    Simple wrapper around getattr to ensure that internal filtering methods return consistent
    types.
    """
    return FilterGetResult(getattr(obj, path))


def get(obj: Any, path: str) -> Any:
    """
    Get a path in obj using dot notation. In case of nested list or tuple, item may be specified by
    numeric index, otherwise the contents of the array are returned along with the unresolved path
    component.

    e.g.
        obj = {'foo': {'bar': '1'}, 'foo.bar': '2', 'foobar': ['first', 'second', 'third']}

        path = 'foo.bar' returns '1'
        path = 'foo\\.bar' returns '2'
        path = 'foobar.0' returns 'first'
    """
    data = get_impl(obj, path)
    return data.result if data.result is not undefined else None


def select_path(obj: _Entry, path: str) -> tuple[list[str], Any]:
    keys = []
    right = path
    cur = obj
    while right:
        left, right = partition(right)
        if isinstance(cur, dict):
            cur = cur.get(left, MatchNotFound)
            keys.append(left)
        elif isinstance(cur, (list, tuple)):
            raise ValueError('Selecting by list index is not supported')

    return (keys, cur)


@overload
def casefold(obj: _T) -> _T: ...


@overload
def casefold(obj: tuple[str]) -> list[str]: ...


def casefold(obj: str | list[str] | tuple[str] | None) -> str | list[str] | None:
    if obj is None:
        return None

    if isinstance(obj, str):
        return obj.casefold()

    if isinstance(obj, (list, tuple)):
        return [x.casefold() for x in obj]

    raise ValueError(f'{type(obj)}: support for casefolding object type not implemented.')


class filters:
    @staticmethod
    def op_in(x, y):
        return operator.contains(y, x)

    @staticmethod
    def op_rin(x, y):
        if x is None:
            return False

        return operator.contains(x, y)

    @staticmethod
    def op_nin(x, y):
        if x is None:
            return False

        return not operator.contains(y, x)

    @staticmethod
    def op_rnin(x, y):
        if x is None:
            return False

        return not operator.contains(x, y)

    @staticmethod
    def op_re(x, y):
        # Some string fields are nullable. If this is the case then we will treat the null as an empty string
        # so that the regex match doesn't raise an exception.
        return re.match(y, x or '')

    @staticmethod
    def op_startswith(x, y):
        if x is None:
            return False

        return x.startswith(y)

    @staticmethod
    def op_notstartswith(x, y):
        if x is None:
            return False

        return not x.startswith(y)

    @staticmethod
    def op_endswith(x, y):
        if x is None:
            return False

        return x.endswith(y)

    @staticmethod
    def op_notendswith(x, y):
        if x is None:
            return False

        return not x.endswith(y)

    opmap = {
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
    }

    def validate_filters(self, filters: Iterable[Sequence], recursion_depth: int = 0, value_maps: dict | None = None):
        """
        This method gets called when `query-filters` gets validated in
        the accepts() decorator of public API endpoints. It is generally
        a good idea to improve validation here, but not at significant
        expense of performance as this is called every time `filter_list`
        is called.
        """
        if recursion_depth > MAX_FILTERS_DEPTH:
            raise ValueError('query-filters max recursion depth exceeded')

        for f in filters:
            if len(f) == 2:
                op, value = f
                if op != 'OR':
                    raise ValueError(f'Invalid operation: {op}')

                if not value:
                    raise ValueError('OR filter requires at least one branch.')

                for branch in value:
                    if isinstance(branch[0], list):
                        self.validate_filters(branch, recursion_depth + 1, value_maps)
                    else:
                        self.validate_filters([branch], recursion_depth + 1, value_maps)

                continue

            elif len(f) != 3:
                raise ValueError(f'Invalid filter {f}')

            op = f[1]
            if op[0] == 'C':
                op = op[1:]
                if op == '~':
                    raise ValueError('Invalid case-insensitive operation: {}'.format(f[1]))

            if op not in self.opmap:
                raise ValueError('Invalid operation: {}'.format(f[1]))

            # special handling for datetime objects
            for operand in (f[0], f[2]):
                if not isinstance(operand, str) or not operand.endswith(TIMESTAMP_DESIGNATOR):
                    continue

                if op not in ['=', '!=', '>', '>=', '<', '<=']:
                    raise ValueError(f'{op}: invalid timestamp operation.')

                other = f[2] if operand == f[0] else f[0]
                # At this point we're just validating that it's an ISO8601 string.
                try:
                    ts = datetime.fromisoformat(other)
                except (TypeError, ValueError):
                    raise ValueError(f'{other}: must be an ISO-8601 formatted timestamp string')

                if value_maps is not None:
                    value_maps[other] = ts

    def validate_select(self, select: _SelectList) -> None:
        for s in select:
            if isinstance(s, str):
                continue

            if isinstance(s, list):
                if len(s) != 2:
                    raise ValueError(
                        f'{s}: A select as list may only contain two parameters: the name '
                        'of the parameter being selected, and the name to which to assign it '
                        'in resulting data.'
                    )

                for idx, selector in enumerate(s):
                    if isinstance(selector, str):
                        continue

                    raise ValueError(
                        f'{s}: {"first" if idx == 0 else "second"} item must be a string.'
                    )

                continue

            raise ValueError(
                f'{s}: selectors must be either a parameter name as a string or '
                'a list containing two items [<parameter name>, <as name>] to emulate '
                'SELECT <parameter name> AS <as name>.'
            )

    def validate_order_by(self, order_by: Iterable[str]) -> None:
        for idx, o in enumerate(order_by):
            if isinstance(o, str):
                continue

            raise ValueError(
                f'{order_by}: parameter at index {idx} [{o}] is not a string.'
            )

    def validate_options(self, options: dict | None) -> tuple[dict, _SelectList, Iterable[str]]:
        if options is None:
            return ({}, [], [])

        if options.get('get') and options.get('limit', 0) > 1:
            raise ValueError(
                'Invalid options combination. `get` implies a single result.'
            )

        if options.get('get') and options.get('offset'):
            raise ValueError(
                'Invalid options combination. `get` implies a single result.'
            )

        select = options.get('select', [])
        self.validate_select(select)
        order_by = options.get('order_by', [])
        self.validate_order_by(order_by)

        return (options, select, order_by)

    def filterop(self, i: object, f: Sequence, source_getter: GetterProtocol) -> bool:
        name, op, value = f
        data = source_getter(i, name)
        if data.result is undefined:
            # Key / attribute doesn't exist in value
            return False

        if not data.done:
            new_filter = [data.key, op, value]
            for entry in data.result:
                if self.filterop(entry, new_filter, source_getter):
                    return True

            return False

        source = data.result
        if op[0] == 'C':
            fn = self.opmap[op[1:]]
            source = casefold(source)
            value = casefold(value)
        else:
            fn = self.opmap[op]

        if fn(source, value):
            return True

        return False

    def getter_fn(self, entry: Any) -> GetterProtocol:
        """
        Evaluate the type of objects returned by iterable and return an
        appropriate function to retrieve attributes so that we can apply filters

        This allows us to filter objects that are not dictionaries.
        """
        if isinstance(entry, dict):
            return get_impl

        return get_attr

    def eval_filter(self, list_item: _Entry, the_filter: Sequence, getter: GetterProtocol, value_maps: dict[str, datetime]):
        """
        `the_filter` in this case will be a single condition of either the form
        [<a>, <opcode>, <b>] or ["OR", [<condition>, <condition>, ...]

        This allows us to do a simple check of list length to determine whether
        we have a conjunction or disjunction.

        value_maps is dict supplied in which to store operands that need to
        be converted into a different type.

        Recursion depth is checked when validate_filters is called above.
        """
        if len(the_filter) == 2:
            # OR check
            op, value = the_filter
            for branch in value:
                if isinstance(branch[0], list):
                    # This branch of OR is a conjunction of
                    # multiple conditions. All of them must be
                    # True in order for branch to be True.
                    hit = all(self.eval_filter(list_item, i, getter, value_maps) for i in branch)
                else:
                    hit = self.eval_filter(list_item, branch, getter, value_maps)

                if hit is True:
                    return True

            # None of conditions in disjunction are True.
            return False

        # Normal condition check
        if not value_maps:
            return self.filterop(list_item, the_filter, getter)

        operand_1 = value_maps.get(the_filter[0]) or the_filter[0]
        operand_2 = value_maps.get(the_filter[2]) or the_filter[2]

        return self.filterop(list_item, (operand_1, the_filter[1], operand_2), getter)

    def do_filters(
        self,
        _list: Iterable[_Entry],
        filters: Iterable[Sequence],
        select: _SelectList,
        shortcircuit: bool,
        value_maps: dict[str, datetime],
    ) -> list[_Entry]:
        rv = []

        # we may be filtering output from a generator and so delay
        # evaluation of what "getter" to use until we begin iteration
        getter = None

        for i in _list:
            if getter is None:
                getter = self.getter_fn(i)
            valid = True
            for f in filters:
                if not self.eval_filter(i, f, getter, value_maps):
                    valid = False
                    break

            if not valid:
                continue

            if select:
                entry = self.do_select([i], select)[0]
            else:
                entry = i

            rv.append(entry)
            if shortcircuit:
                break

        return rv

    def do_select(self, _list: Iterable[_Entry], select: _SelectList) -> list[_Entry]:
        rv = []
        for i in _list:
            entry = {}
            for s in select:
                if isinstance(s, list):
                    target, new_name = s
                else:
                    target = s
                    new_name = None

                keys, value = select_path(i, target)
                if value is MatchNotFound:
                    continue

                if new_name is not None:
                    entry[new_name] = value
                    continue

                last = keys.pop(-1)
                obj = entry
                for k in keys:
                    obj = obj.setdefault(k, {})

                obj[last] = value

            rv.append(entry)

        return rv

    def do_count(self, rv: list[_Entry]) -> int:
        return len(rv)

    def order_nulls(self, _list: list[_Entry], order: str) -> tuple[list[_Entry], list[_Entry]]:
        if order.startswith(REVERSE_CHAR):
            order = order[1:]
            reverse = True
        else:
            reverse = False

        nulls = []
        non_nulls = []
        for entry in _list:
            if entry.get(order) is None:
                nulls.append(entry)
            else:
                non_nulls.append(entry)

        non_nulls = sorted(non_nulls, key=lambda x: get(x, order), reverse=reverse)
        return (nulls, non_nulls)

    def order_no_null(self, _list: list[_Entry], order: str) -> list[_Entry]:
        if order.startswith(REVERSE_CHAR):
            order = order[1:]
            reverse = True
        else:
            reverse = False

        return sorted(_list, key=lambda x: get(x, order), reverse=reverse)

    def do_order(self, rv: list[_Entry], order_by: Iterable[str]) -> list[_Entry]:
        for o in order_by:
            if o.startswith(NULLS_FIRST):
                nulls, non_nulls = self.order_nulls(rv, o[len(NULLS_FIRST):])
                rv = nulls + non_nulls
            elif o.startswith(NULLS_LAST):
                nulls, non_nulls = self.order_nulls(rv, o[len(NULLS_LAST):])
                rv = non_nulls + nulls
            else:
                rv = self.order_no_null(rv, o)

        return rv

    def do_get(self, rv: list[_Entry]) -> _Entry:
        try:
            return rv[0]
        except IndexError:
            raise MatchNotFound() from None

    def filter_list(
        self,
        _list: Iterable[_Entry],
        filters: Iterable[Sequence] | None = None,
        options: dict | None = None
    ) -> list[_Entry] | _Entry | int:
        options, select, order_by = self.validate_options(options)

        do_shortcircuit = options.get('get') and not order_by

        if filters:
            maps = {}
            self.validate_filters(filters, value_maps=maps)
            rv = self.do_filters(_list, filters, select, do_shortcircuit, value_maps=maps)
            if do_shortcircuit:
                return self.do_get(rv)

        elif select:
            rv = self.do_select(_list, select)
        else:
            # Normalize the output to a list. Caller may have passed
            # a generator into this method.
            rv = list(_list)

        if options.get('count') is True:
            return self.do_count(rv)

        rv = self.do_order(rv, order_by)

        if options.get('get') is True:
            return self.do_get(rv)

        if options.get('offset'):
            rv = rv[options['offset']:]

        if options.get('limit'):
            return rv[:options['limit']]

        return rv


filter_list = filters().filter_list


def filter_getattrs(filters: list[Sequence]) -> set:
    """
    Get a set of attributes in a filter list.
    """
    attrs = set()
    if not filters:
        return attrs

    f = filters.copy()
    while f:
        filter_ = f.pop()
        if len(filter_) == 2:
            f.append(filter_[1])
        elif len(filter_) == 3:
            attrs.add(filter_[0])
        else:
            raise ValueError('Invalid filter.')
    return attrs


@functools.cache
def sw_info():
    """Returns the various software information from the manifest file."""
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)
        version = manifest['version']
        return {
            'stable': 'MASTER' not in manifest['version'],
            'codename': manifest['codename'],
            'version': version,
            'fullname': f'{BRAND}-{version}',
            'buildtime': manifest['buildtime'],
        }


def sw_buildtime():
    return sw_info()['buildtime']


def sw_version() -> str:
    return sw_info()['fullname']


def are_indices_in_consecutive_order(arr: Sequence[int]) -> bool:
    """
    Determine if the integers in an array form a consecutive sequence 
    with respect to their indices.

    This function checks whether each integer at a given index position is 
    exactly one greater than the integer at the previous index. In other 
    words, it verifies that the sequence of numbers increases by exactly one 
    as you move from left to right through the array.

    Parameters:
    arr (list[int]): A list of integers whose index-based order needs to be 
                     validated.

    Returns:
    bool: 
        - True if the numbers are consecutive.
        - False if any number does not follow the previous number by exactly one.

    Examples:
    >>> are_indices_in_consecutive_order([1, 2])
    True

    >>> are_indices_in_consecutive_order([1, 3])
    False

    >>> are_indices_in_consecutive_order([5, 6, 7])
    True

    >>> are_indices_in_consecutive_order([4, 6, 7])
    False

    Edge Cases:
    - An empty array will return True as there are no elements to violate 
      the order.
    - A single-element array will also return True for the same reason.

    Notes:
    - The function does not modify the input array and operates in O(n) time
      complexity, where n is the number of elements in the list.
    """
    for i in range(1, len(arr)):
        if arr[i] != arr[i - 1] + 1:
            return False
    return True


class Nid:

    def __init__(self, _id: int):
        self._id = _id

    def __call__(self) -> int:
        num = self._id
        self._id += 1
        return num
