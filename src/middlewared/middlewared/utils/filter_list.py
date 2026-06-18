from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, Literal, Mapping, Required, Sequence, TypedDict, TypeVar, overload

import truenas_pyfilter as _tf
from truenas_pyfilter import CompiledFilters, CompiledOptions, match  # noqa: F401 (re-exported)

from middlewared.api.base.validators.filters import TIMESTAMP_DESIGNATOR
from middlewared.service_exception import MatchNotFound

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel
    from middlewared.api.current import QueryOptions

    _Entry = TypeVar('_Entry', bound=Mapping[str, Any] | type[BaseModel])
else:
    _Entry = TypeVar('_Entry')

CF_EMPTY: CompiledFilters = _tf.compile_filters([])
CO_EMPTY: CompiledOptions = _tf.compile_options()


_TIMESTAMP_OPS = frozenset(('=', '!=', '<', '>', '<=', '>='))


def _preprocess_date_filters(filters: Sequence[Any], depth: int = 0) -> list[Sequence[Any]] | None:
    """
    Walk a filter tree for .$date operands; return a rebuilt tree with suffixes stripped
    and ISO strings replaced with datetime objects, or None if no .$date was found.

    e.g. ["expires.$date", ">", "2024-01-01T00:00:00"] ->
         ["expires", ">", datetime(2024, 1, 1)]
    """
    if depth > 3:
        raise ValueError('query-filters max recursion depth exceeded')

    result: list[Sequence[object]] = []
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
    filters: Sequence[Sequence[Any]] | None,
    options: _FilterListCountOptions,
) -> int: ...


@overload
def filter_list(
    _list: Iterable[_Entry],
    filters: Sequence[Sequence[Any]] | None,
    options: _FilterListGetOptions,
) -> _Entry: ...


@overload
def filter_list(
    _list: Iterable[_Entry],
    filters: Sequence[Sequence[Any]] | None = None,
    options: None = None,
) -> list[_Entry]: ...


@overload
def filter_list(
    _list: Iterable[_Entry],
    filters: Sequence[Sequence[Any]] | None = None,
    options: dict[str, Any] | None = None,
) -> list[_Entry] | _Entry | int: ...


@overload
def filter_list[E: BaseModel](
    _list: Iterable[E],
    filters: Sequence[Sequence[Any]],
    options: QueryOptions,
    model: type[BaseModel],
) -> list[E] | E | int: ...


def filter_list(
    _list: Iterable[Any],
    filters: Sequence[Sequence[Any]] | None = None,
    options: dict[str, Any] | _FilterListGetOptions | _FilterListCountOptions | QueryOptions | None = None,
    model: type[BaseModel] | None = None,
) -> Any:
    """Main entry point for filtering, selecting, ordering and paginating data collections."""
    cf = compile_filters(list(filters or []), model=model)
    co = compile_options(options or {}, model=model)
    rv = _tf.tnfilter(_list, filters=cf, options=co)
    if isinstance(rv, int):
        return rv   # count=True: tnfilter returns int directly
    if co.get:
        try:
            return rv[0]
        except IndexError:
            raise MatchNotFound() from None
    return rv


def compile_filters(filters: list[Sequence[Any]], model: type[BaseModel] | None = None) -> CompiledFilters:
    """
    Validate and pre-compile a filter list for reuse. Handles .$date preprocessing.
    Store the returned object at module or class level to avoid recompiling on every call.
    """
    if not filters:
        return CF_EMPTY

    if (preprocessed := _preprocess_date_filters(filters)) is not None:
        filters = preprocessed

    return _tf.compile_filters(filters, model=model)


def compile_options(
    options: dict[str, Any] | _FilterListGetOptions | _FilterListCountOptions | QueryOptions | None = None,
    model: type[BaseModel] | None = None,
) -> _tf.CompiledOptions:
    """
    Pre-compile query options for reuse. Validation is performed by the C layer.
    Store the returned object at module or class level to avoid recompiling on every call.
    """
    from middlewared.api.current import QueryOptions

    if options is None:
        return CO_EMPTY

    if isinstance(options, dict):
        # Eventually, get rid of this branch
        options_inst = QueryOptions.model_validate({
            k: v for k, v in options.items() if k not in {"extend", "extend_context", "extend_fk", "prefix"}
        })
    else:
        options_inst = options

    return _tf.compile_options(
        get=options_inst.get,
        count=options_inst.count,
        select=options_inst.select,
        order_by=options_inst.order_by,
        offset=options_inst.offset,
        limit=options_inst.limit,
        model=model,
    )


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
