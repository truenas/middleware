import pytest

from middlewared.plugins.reporting.utils import get_metrics_approximation, calculate_disk_space_for_netdata


@pytest.mark.parametrize('disk_count,core_count,interface_count,pool_count,services_count,vms_count,expected_output', [
    (4, 2, 1, 2, 10, 2, {1: 699, 300: 10}),
    (1600, 32, 4, 4, 10, 1, {1: 8754, 300: 1612}),
    (10, 16, 2, 2, 12, 3, {1: 838, 300: 16}),
])
def test_netdata_metrics_count_approximation(
    disk_count, core_count, interface_count, pool_count, services_count, vms_count, expected_output
):
    assert get_metrics_approximation(
        disk_count, core_count, interface_count, pool_count, vms_count, services_count
    ) == expected_output


@pytest.mark.parametrize(
    'disk_count,core_count,interface_count,pool_count,services_count,vms_count,days,'
    'bytes_per_point,tier_interval,expected_output', [
        (4, 2, 1, 2, 10, 2, 7, 1, 1, 403),
        (4, 2, 1, 2, 10, 1, 7, 4, 60, 25),
        (1600, 32, 4, 12, 2, 4, 4, 1, 1, 2918),
        (1600, 32, 4, 10, 1, 4, 4, 4, 900, 12),
        (10, 16, 2, 2, 12, 1, 3, 1, 1, 183),
        (10, 16, 2, 2, 10, 3, 3, 4, 60, 13),
        (1600, 32, 4, 4, 12, 3, 18, 1, 1, 13151),
        (1600, 32, 4, 4, 12, 1, 18, 4, 900, 57),
    ],
)
def test_netdata_disk_space_approximation(
        disk_count, core_count, interface_count, pool_count, services_count,
        vms_count, days, bytes_per_point, tier_interval, expected_output
):
    assert calculate_disk_space_for_netdata(get_metrics_approximation(
        disk_count, core_count, interface_count, pool_count, vms_count, services_count
    ), days, bytes_per_point, tier_interval) == expected_output


@pytest.mark.parametrize(
    'disk_count,core_count,interface_count,pool_count,services_count,vms_count,days,bytes_per_point,tier_interval',
    [
        (4, 2, 1, 2, 10, 2, 7, 1, 1),
        (4, 2, 1, 2, 12, 2, 7, 4, 60),
        (1600, 32, 4, 4, 10, 3, 4, 1, 1),
        (1600, 32, 4, 4, 12, 3, 4, 4, 900),
        (10, 16, 2, 2, 10, 4, 3, 1, 1),
        (10, 16, 2, 2, 12, 4, 3, 4, 60),
        (1600, 32, 4, 4, 10, 5, 18, 1, 1),
        (1600, 32, 4, 4, 12, 5, 18, 4, 900),
    ],
)
def test_netdata_days_approximation(
        disk_count, core_count, interface_count, pool_count, services_count, vms_count, days, bytes_per_point,
        tier_interval):
    metric_intervals = get_metrics_approximation(
        disk_count, core_count, interface_count, pool_count, vms_count, services_count
    )
    disk_size = calculate_disk_space_for_netdata(metric_intervals, days, bytes_per_point, tier_interval)
    total_metrics = metric_intervals[1] + (metric_intervals[300] / 300)
    assert round((disk_size * 1024 * 1024) / (bytes_per_point * total_metrics * (86400 / tier_interval))) == days
