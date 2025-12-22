from datetime import datetime
from typing import Any, Iterable, NamedTuple, overload, Protocol, Sequence, TypeVar

from middlewared.api.base.validators.filters import validate_filters
from middlewared.api.base.validators.filter_ops import opmap
from middlewared.api.base.validators.options import _SelectList, validate_options
from middlewared.service_exception import MatchNotFound
from .lang import undefined


NULLS_FIRST = 'nulls_first:'
NULLS_LAST = 'nulls_last:'
REVERSE_CHAR = '-'

_T = TypeVar('_T', str, list[str], None)
_Entry = dict[str, Any]


class FilterGetResult(NamedTuple):
    result: Any
    key: str | None = None
    done: bool = True


class GetterProtocol(Protocol):
    def __call__(self, obj: object, path: str) -> FilterGetResult: ...


@overload
def casefold(obj: _T) -> _T: ...


@overload
def casefold(obj: tuple[str]) -> list[str]: ...


def casefold(obj: str | list[str] | tuple[str] | None) -> str | list[str] | None:
    """Convert string or string collection to lowercase for case-insensitive filtering operations."""
    if obj is None:
        return None

    if isinstance(obj, str):
        return obj.casefold()

    if isinstance(obj, (list, tuple)):
        return [x.casefold() for x in obj]

    raise ValueError(f'{type(obj)}: support for casefolding object type not implemented.')


def partition(s: str) -> tuple[str, str]:
    """Split dotted path string into left and right components, handling escaped dots."""
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
    """Navigate nested dictionary/list structures using dot notation paths."""
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
    r"""
    Get a path in obj using dot notation. In case of nested list or tuple, item may be specified by
    numeric index, otherwise the contents of the array are returned along with the unresolved path
    component.

    e.g.
        obj = {'foo': {'bar': '1'}, 'foo.bar': '2', 'foobar': ['first', 'second', 'third']}

        path = 'foo.bar' returns '1'
        path = 'foo\.bar' returns '2'
        path = 'foobar.0' returns 'first'
    """
    data = get_impl(obj, path)
    return data.result if data.result is not undefined else None


def select_path(obj: _Entry, path: str) -> tuple[list[str], Any]:
    """Extract value from nested dictionary and return the key path and value."""
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


def filterop(i: object, f: Sequence, source_getter: GetterProtocol) -> bool:
    """Apply a single filter operation to an object and return whether it matches."""
    name, op, value = f
    data = source_getter(i, name)
    if data.result is undefined:
        # Key / attribute doesn't exist in value
        return False

    if not data.done:
        new_filter = [data.key, op, value]
        for entry in data.result:
            if filterop(entry, new_filter, source_getter):
                return True

        return False

    source = data.result
    if op[0] == 'C':
        fn = opmap[op[1:]]
        source = casefold(source)
        value = casefold(value)
    else:
        fn = opmap[op]

    if fn(source, value):
        return True

    return False


def getter_fn(entry: Any) -> GetterProtocol:
    """
    Evaluate the type of objects returned by iterable and return an
    appropriate function to retrieve attributes so that we can apply filters

    This allows us to filter objects that are not dictionaries.
    """
    if isinstance(entry, dict):
        return get_impl

    return get_attr


def eval_filter(
    list_item: _Entry,
    the_filter: Sequence,
    getter: GetterProtocol,
    value_maps: dict[str, datetime] | None = None
):
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
                hit = all(eval_filter(list_item, i, getter, value_maps) for i in branch)
            else:
                hit = eval_filter(list_item, branch, getter, value_maps)

            if hit is True:
                return True

        # None of conditions in disjunction are True.
        return False

    # Normal condition check
    if not value_maps:
        return filterop(list_item, the_filter, getter)

    # Use datetime objects for filter operation
    operand_1 = value_maps.get(the_filter[0]) or the_filter[0]
    operand_2 = value_maps.get(the_filter[2]) or the_filter[2]

    return filterop(list_item, (operand_1, the_filter[1], operand_2), getter)


def do_filters(
    _list: Iterable[_Entry],
    filters: Iterable[Sequence],
    select: _SelectList | None = None,
    shortcircuit: bool = False,
    value_maps: dict[str, datetime] | None = None,
) -> list[_Entry]:
    """Filter a list of entries based on the provided filter conditions."""
    rv = []

    # we may be filtering output from a generator and so delay
    # evaluation of what "getter" to use until we begin iteration
    getter = None

    for i in _list:
        if getter is None:
            getter = getter_fn(i)
        valid = True
        for f in filters:
            if not eval_filter(i, f, getter, value_maps):
                valid = False
                break

        if not valid:
            continue

        if select:
            entry = do_select([i], select)[0]
        else:
            entry = i

        rv.append(entry)
        if shortcircuit:
            break

    return rv


def do_select(_list: Iterable[_Entry], select: _SelectList) -> list[_Entry]:
    """Project specific fields from entries creating new dictionaries with selected data."""
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


def do_count(rv: list[_Entry]) -> int:
    """Return the count of entries in the result list."""
    return len(rv)


def order_nulls(_list: list[_Entry], order: str) -> tuple[list[_Entry], list[_Entry]]:
    """Separate and sort entries with null values from non-null values for a field."""
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


def order_no_null(_list: list[_Entry], order: str) -> list[_Entry]:
    """Sort entries by a field without special handling for null values."""
    original_order = order
    if order.startswith(REVERSE_CHAR):
        order = order[1:]
        reverse = True
    else:
        reverse = False

    try:
        return sorted(_list, key=lambda x: get(x, order), reverse=reverse)
    except TypeError as e:
        if "not supported between instances of 'NoneType'" in str(e):
            raise ValueError(
                f'Cannot sort by {original_order!r} because the field contains null values. '
                f'Please use "nulls_first:{original_order}" or "nulls_last:{original_order}" to specify null placement.'
            ) from e
        raise


def do_order(rv: list[_Entry], order_by: Iterable[str]) -> list[_Entry]:
    """Apply multiple ordering operations to a result list including null placement handling."""
    for o in order_by:
        if o.startswith(NULLS_FIRST):
            nulls, non_nulls = order_nulls(rv, o[len(NULLS_FIRST):])
            rv = nulls + non_nulls
        elif o.startswith(NULLS_LAST):
            nulls, non_nulls = order_nulls(rv, o[len(NULLS_LAST):])
            rv = non_nulls + nulls
        else:
            rv = order_no_null(rv, o)

    return rv


def do_get(rv: list[_Entry]) -> _Entry:
    """Return the first entry from the result list or raise MatchNotFound if empty."""
    try:
        return rv[0]
    except IndexError:
        raise MatchNotFound() from None


def filter_list(
    _list: Iterable[_Entry],
    filters: Iterable[Sequence] | None = None,
    options: dict | None = None
) -> list[_Entry] | _Entry | int:
    """Main entry point for filtering, selecting, ordering and paginating data collections."""
    options, select, order_by = validate_options(options)

    do_shortcircuit = options.get('get', False) and not order_by

    if filters:
        maps = {}
        validate_filters(filters, value_maps=maps)
        rv = do_filters(_list, filters, select, do_shortcircuit, value_maps=maps)
        if do_shortcircuit:
            return do_get(rv)

    elif select:
        rv = do_select(_list, select)
    else:
        # Normalize the output to a list. Caller may have passed
        # a generator into this method.
        rv = list(_list)

    if options.get('count') is True:
        return do_count(rv)

    rv = do_order(rv, order_by)

    if options.get('get') is True:
        return do_get(rv)

    if options.get('offset'):
        rv = rv[options['offset']:]

    if options.get('limit'):
        return rv[:options['limit']]

    return rv


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
