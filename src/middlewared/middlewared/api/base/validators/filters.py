import truenas_pyfilter as _tf

TIMESTAMP_DESIGNATOR = '.$date'


def validate_filters(filters, recursion_depth=0, value_maps=None):
    _tf.compile_filters(list(filters))
    return filters
