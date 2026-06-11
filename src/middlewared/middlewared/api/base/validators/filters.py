from typing import Any

import truenas_pyfilter as _tf

TIMESTAMP_DESIGNATOR = '.$date'


def validate_filters(filters: list[Any]) -> list[Any]:
    _tf.compile_filters(list(filters))
    return filters
