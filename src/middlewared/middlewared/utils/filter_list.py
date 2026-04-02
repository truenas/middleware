from datetime import datetime
from typing import Any, Iterable, overload, Sequence, TypeVar, Literal, Required, TypedDict

import truenas_pyfilter as _tf
from truenas_pyfilter import CompiledFilters, CompiledOptions, match  # noqa: F401 (re-exported)

from middlewared.api.base.validators.filters import TIMESTAMP_DESIGNATOR
from middlewared.api.base.validators.options import _SelectList, validate_options
from middlewared.service_exception import MatchNotFound

# Pre-built compiled objects for the common match-all / no-op case.
# Use these instead of calling _tf.compile_filters([]) / _tf.compile_options() per call.
CF_EMPTY: CompiledFilters = _tf.compile_filters([])
CO_EMPTY: CompiledOptions = _tf.compile_options()

_Entry = TypeVar('_Entry', bound=dict[str, Any])


def _build_compiled_options(
    options: dict,
    select: _SelectList,
    order_by: Iterable[str],
) -> CompiledOptions:
    sel = list(select)
    ord_ = list(order_by)
    return _tf.compile_options(
        get=options.get('get', False),
        count=options.get('count', False),
        select=sel if sel else None,
        order_by=ord_ if ord_ else None,
        offset=options.get('offset', 0),
        limit=options.get('limit', 0),
    )


_TIMESTAMP_OPS = frozenset(('=', '!=', '<', '>', '<=', '>='))


def _preprocess_date_filters(filters: Iterable[Sequence[Any]], depth: int = 0) -> list | None:
    """
    Walk a filter tree for .$date operands; return a rebuilt tree with suffixes stripped
    and ISO strings replaced with datetime objects, or None if no .$date was found.

    e.g. ["expires.$date", ">", "2024-01-01T00:00:00"] ->
         ["expires", ">", datetime(2024, 1, 1)]
    """
    if depth > 3:
        raise ValueError('query-filters max recursion depth exceeded')

    result = []
    changed = False
    for f in filters:
        if len(f) == 2 and isinstance(f[0], str) and f[0] == 'OR':
            # OR node: ['OR', [branch, ...]]
            sub = _preprocess_date_filters(f[1], depth + 1)
            result.append([f[0], sub if sub is not None else list(f[1])])
            if sub is not None:
                changed = True
        elif f and isinstance(f[0], list):
            # AND group inside OR: [[filter, ...], ...]
            sub = _preprocess_date_filters(f, depth + 1)
            result.append(sub if sub is not None else list(f))
            if sub is not None:
                changed = True
        else:
            field, op, value = f
            if isinstance(field, str) and field.endswith(TIMESTAMP_DESIGNATOR):
                if op not in _TIMESTAMP_OPS:
                    raise ValueError(f'{op}: invalid timestamp operation.')
                if not isinstance(value, str):
                    raise ValueError(
                        f'{value}: must be an ISO-8601 formatted timestamp string'
                    )
                field = field[:-len(TIMESTAMP_DESIGNATOR)]
                try:
                    value = datetime.fromisoformat(value)
                except ValueError:
                    raise ValueError(
                        f'{value}: must be an ISO-8601 formatted timestamp string'
                    ) from None
                changed = True
            result.append([field, op, value])
    return result if changed else None


class _FilterListBaseOptions(TypedDict, total=False):
    select: list[str | list[str]]
    order_by: list[str]
    offset: int
    limit: int
    force_sql_filters: bool
    relationships: bool
    extend: str | None
    extend_context: str | None
    prefix: str | None
    extra: dict[str, Any]


class _FilterListGetOptions(_FilterListBaseOptions, total=False):
    get: Required[Literal[True]]
    count: Literal[False]


class _FilterListCountOptions(_FilterListBaseOptions, total=False):
    count: Required[Literal[True]]
    get: Literal[False]


@overload
def filter_list(
    _list: Iterable[_Entry],
    filters: Iterable[Sequence[Any]] | None,
    options: _FilterListCountOptions,
) -> int: ...


@overload
def filter_list(
    _list: Iterable[_Entry],
    filters: Iterable[Sequence[Any]] | None,
    options: _FilterListGetOptions,
) -> _Entry: ...


@overload
def filter_list(
    _list: Iterable[_Entry],
    filters: Iterable[Sequence[Any]] | None = None,
    options: None = None,
) -> list[_Entry]: ...


@overload
def filter_list(
    _list: Iterable[_Entry],
    filters: Iterable[Sequence[Any]] | None = None,
    options: dict[str, Any] | None = None,
) -> list[_Entry] | _Entry | int: ...


def filter_list(
    _list: Iterable[_Entry],
    filters: Iterable[Sequence[Any]] | None = None,
    options: dict[str, Any] | _FilterListGetOptions | _FilterListCountOptions | None = None
) -> list[_Entry] | _Entry | int:
    """Main entry point for filtering, selecting, ordering and paginating data collections."""
    options, select, order_by = validate_options(options)  # type: ignore[arg-type]

    if filters:
        if (preprocessed := _preprocess_date_filters(filters)) is not None:
            filters = preprocessed

    cf = _tf.compile_filters(list(filters) if filters else [])
    co = _build_compiled_options(options, select, order_by)  # type: ignore[arg-type]
    rv = _tf.tnfilter(_list, filters=cf, options=co)
    if isinstance(rv, int):
        return rv   # count=True: tnfilter returns int directly
    if options.get('get') is True:
        try:
            return rv[0]
        except IndexError:
            raise MatchNotFound() from None
    return rv


def compile_filters(filters: list) -> CompiledFilters:
    """
    Validate and pre-compile a filter list for reuse. Handles .$date preprocessing.
    Store the returned object at module or class level to avoid recompiling on every call.
    """
    if (preprocessed := _preprocess_date_filters(filters)) is not None:
        filters = preprocessed
    return _tf.compile_filters(filters)


def compile_options(options: dict | None = None) -> CompiledOptions:
    """
    Pre-compile query options for reuse. Validation is performed by the C layer.
    Store the returned object at module or class level to avoid recompiling on every call.
    """
    options = options or {}
    return _tf.compile_options(
        get=options.get('get', False),
        count=options.get('count', False),
        select=options.get('select') or None,
        order_by=options.get('order_by') or None,
        offset=options.get('offset', 0),
        limit=options.get('limit', 0),
    )


def filter_list_compiled(
    _list: Iterable[_Entry],
    compiled_filters: CompiledFilters,
    compiled_options: CompiledOptions,
) -> list[_Entry] | int:
    """
    Filter an iterable using pre-compiled filters and options. Skips all validation.
    Use when compiled_filters / compiled_options are stored persistently (e.g. module-level).
    For single-item boolean checks use match() instead.
    """
    return _tf.tnfilter(_list, filters=compiled_filters, options=compiled_options)


def filter_getattrs(filters: list[Sequence[Any]]) -> set[str]:
    """
    Get a set of attributes in a filter list.
    """
    attrs: set[str] = set()
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
