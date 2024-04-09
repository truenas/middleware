import pytest

from middlewared.plugins.reporting.utils import get_metrics_approximation, calculate_disk_space_for_netdata


@pytest.mark.parametrize('disk_count,core_count,interface_count,pool_count,expected_output', [
    (4, 2, 1, 2, {1: 370, 60: 4}),
    (1600, 32, 4, 4, {1: 44017, 60: 1600}),
    (10, 16, 2, 2, {1: 777, 60: 10}),
])
def test_netdata_metrics_count_approximation(disk_count, core_count, interface_count, pool_count, expected_output):
    assert get_metrics_approximation(disk_count, core_count, interface_count, pool_count) == expected_output


@pytest.mark.parametrize(
    'disk_count,core_count,interface_count,pool_count,days,bytes_per_point,tier_interval,expected_output', [
        (4, 2, 1, 2, 7, 1, 1, 213),
        (4, 2, 1, 2, 7, 4, 60, 14),
        (1600, 32, 4, 4, 4, 1, 1, 14516),
        (1600, 32, 4, 4, 4, 4, 900, 64),
        (10, 16, 2, 2, 3, 1, 1, 192),
        (10, 16, 2, 2, 3, 4, 60, 12),
        (1600, 32, 4, 4, 18, 1, 1, 65323),
        (1600, 32, 4, 4, 18, 4, 900, 290),
    ],
)
def test_netdata_disk_space_approximation(
    disk_count, core_count, interface_count, pool_count, days, bytes_per_point, tier_interval, expected_output
):
    assert calculate_disk_space_for_netdata(get_metrics_approximation(
        disk_count, core_count, interface_count, pool_count
    ), days, bytes_per_point, tier_interval) == expected_output


@pytest.mark.parametrize(
    'disk_count,core_count,interface_count,pool_count,days,bytes_per_point,tier_interval', [
        (4, 2, 1, 2, 7, 1, 1),
        (4, 2, 1, 2, 7, 4, 60),
        (1600, 32, 4, 4, 4, 1, 1),
        (1600, 32, 4, 4, 4, 4, 900),
        (10, 16, 2, 2, 3, 1, 1),
        (10, 16, 2, 2, 3, 4, 60),
        (1600, 32, 4, 4, 18, 1, 1),
        (1600, 32, 4, 4, 18, 4, 900),
    ],
)
def test_netdata_days_approximation(
    disk_count, core_count, interface_count, pool_count, days, bytes_per_point, tier_interval
):
    metric_intervals = get_metrics_approximation(disk_count, core_count, interface_count, pool_count)
    disk_size = calculate_disk_space_for_netdata(metric_intervals, days, bytes_per_point, tier_interval)
    total_metrics = metric_intervals[1] + (metric_intervals[60] / 60)
    assert round((disk_size * 1024 * 1024) / (bytes_per_point * total_metrics * (86400 / tier_interval))) == days
