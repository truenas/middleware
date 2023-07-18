import contextlib
import typing


def safely_retrieve_dimension(
    all_metrics: dict, chart: str, dimension: typing.Optional[str] = None, default: typing.Optional[typing.Any] = None
) -> typing.Any:
    """
    Safely retrieve a dimension from a chart. If the dimension is not found, return the default value
    and if no dimension is explicitly provided, return all the dimensions found for the chart.
    """
    with contextlib.suppress(KeyError):
        if dimension:
            return all_metrics[chart]['dimensions'][dimension]['value']
        else:
            return {
                dimension_name: value['value']
                for dimension_name, value in all_metrics[chart]['dimensions'].items()
            }

    return default


def normalize_value(
    value: int, multiplier: int = 1, divisor: int = 1, absolute: bool = True, round_value: bool = True,
) -> typing.Union[int, float]:
    normalized = (value / divisor) * multiplier
    if absolute:
        normalized = abs(normalized)
    if round_value:
        normalized = round(normalized)
    return normalized
