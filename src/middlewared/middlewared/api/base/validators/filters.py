from datetime import datetime
from typing import Iterable, Sequence, TypeVar

from .filter_ops import opmap

MAX_FILTERS_DEPTH = 3
TIMESTAMP_DESIGNATOR = '.$date'

_Filters = TypeVar('_Filters', bound=Iterable[Sequence])


def validate_filters(filters: _Filters, recursion_depth: int = 0, value_maps: dict | None = None) -> _Filters:
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
                    validate_filters(branch, recursion_depth + 1, value_maps)
                else:
                    validate_filters([branch], recursion_depth + 1, value_maps)

            continue

        elif len(f) != 3:
            raise ValueError(f'Invalid filter {f}')

        op = f[1]
        if op[0] == 'C':
            op = op[1:]
            if op == '~':
                raise ValueError('Invalid case-insensitive operation: {}'.format(f[1]))

        if op not in opmap:
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

    return filters
