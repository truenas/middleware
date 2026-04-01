from typing import Iterable

import truenas_pyfilter as _tf

MAX_LIMIT = 10000
_SelectList = Iterable[str | list[str]]


def validate_options(options: dict | None) -> tuple[dict, _SelectList, Iterable[str]]:
    if options is None:
        return {}, [], []
    select = options.get('select', [])
    order_by = options.get('order_by', [])
    _tf.compile_options(
        get=options.get('get', False),
        count=options.get('count', False),
        select=list(select) or None,
        order_by=list(order_by) or None,
        offset=options.get('offset', 0),
        limit=options.get('limit', 0),
    )
    return options, select, order_by
