from __future__ import annotations

import collections
import errno
import time
import typing

from middlewared.api.current import (
    GraphIdentifier,
    QueryOptions,
    ReportingGetDataResponse,
    ReportingQuery,
)
from middlewared.service import CallError, ServiceContext, ValidationErrors
from middlewared.utils.filter_list import filter_list

from .netdata import GRAPH_PLUGINS
from .netdata.graph_base import GraphBase
from .utils import convert_unit, fetch_data_from_graph_plugins

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware

T = typing.TypeVar('T')


def to_entries(
    result: list[dict[str, typing.Any]] | dict[str, typing.Any] | int, model: type[T],
) -> list[T] | T | int:
    # filterable result models expect the `__query_result_item__` variant of the item model,
    # not the plain item; constructing the plain model fails serialization validation.
    constructor = typing.cast(type[T], getattr(model, '__query_result_item__', model))
    if isinstance(result, int):
        return result
    if isinstance(result, dict):
        return constructor(**result)
    return [constructor(**row) for row in result]


def build_graphs(middleware: Middleware) -> dict[str, GraphBase]:
    return {name: klass(middleware) for name, klass in GRAPH_PLUGINS.items()}


def graph_names(graphs: dict[str, GraphBase]) -> list[str]:
    return list(graphs.keys())


def translate_query_params(query: ReportingQuery) -> dict[str, typing.Any]:
    # TODO: Add unit tests for this please
    start_time = 0
    unit = query.unit
    if unit:
        verrors = ValidationErrors()
        for i in ('start', 'end'):
            if getattr(query, i) is not None:
                verrors.add(
                    f'reporting_query.{i}',
                    f'{i!r} should only be used if "unit" attribute is not provided.',
                )
        verrors.check()
    elif query.start is None:
        unit = 'HOUR'
    else:
        start_time = int(query.start)

    end_time = int(query.end or time.time())
    return {
        'before': end_time,
        'after': end_time - convert_unit(unit, query.page) if unit else start_time,
    }


async def _export(
    context: ServiceContext, graph_plugin: GraphBase, query: ReportingQuery,
) -> list[dict[str, typing.Any]]:
    query_params = translate_query_params(query)
    await graph_plugin.build_context()
    no_identifiers: list[str | None] = [None]
    identifiers = await graph_plugin.get_identifiers() if graph_plugin.uses_identifiers else no_identifiers
    return await graph_plugin.export_multiple_identifiers(query_params, identifiers or [], query.aggregate)


async def netdata_graph(
    context: ServiceContext, graphs: dict[str, GraphBase], name: str, query: ReportingQuery,
) -> list[ReportingGetDataResponse]:
    graph_plugin = graphs.get(name)
    if graph_plugin is None:
        raise CallError(f'{name!r} is not a valid graph plugin.', errno.ENOENT)

    return [ReportingGetDataResponse.model_validate(d) for d in await _export(context, graph_plugin, query)]


async def netdata_graphs(
    graphs: dict[str, GraphBase], filters: list[typing.Any], options: QueryOptions,
) -> list[dict[str, typing.Any]] | dict[str, typing.Any] | int:
    return filter_list([await i.as_dict() for i in graphs.values()], filters, options.model_dump())


async def netdata_get_data(
    context: ServiceContext, graphs: dict[str, GraphBase], graphs_arg: list[GraphIdentifier], query: ReportingQuery,
) -> list[ReportingGetDataResponse]:
    query_params = translate_query_params(query)
    graph_plugins: dict[GraphBase, list[str | None]] = collections.defaultdict(list)
    for graph in graphs_arg:
        plugin = graphs.get(graph.name)
        if plugin is None:
            raise CallError(f'{graph.name!r} is not a valid graph plugin.', errno.ENOENT)
        graph_plugins[plugin].append(graph.identifier)

    results: list[ReportingGetDataResponse] = []
    async for result in fetch_data_from_graph_plugins(graph_plugins, query_params, query.aggregate):
        results.extend(ReportingGetDataResponse.model_validate(d) for d in result)

    return results


async def netdata_get_all(
    context: ServiceContext, graphs: dict[str, GraphBase], query: ReportingQuery,
) -> list[dict[str, typing.Any]]:
    rv: list[dict[str, typing.Any]] = []
    for graph_plugin in graphs.values():
        rv.extend(await _export(context, graph_plugin, query))
    return rv
