import pytest

from middlewared.plugins.reporting.utils import get_metrics_approximation, calculate_disk_space_for_netdata


@pytest.mark.parametrize('disk_count,core_count,interface_count,pool_count,expected_output', [
    (4, 2, 1, 2, {1: 354, 1800: 4}),
    (1600, 32, 4, 4, {1: 44001, 1800: 1600}),
    (10, 16, 2, 2, {1: 761, 1800: 10}),
])
def test_netdata_metrics_count_approximation(disk_count, core_count, interface_count, pool_count, expected_output):
    assert get_metrics_approximation(disk_count, core_count, interface_count, pool_count) == expected_output


@pytest.mark.parametrize('disk_count,core_count,interface_count,pool_count,days,expected_output', [
    (4, 2, 1, 2, 7, 204),
    (1600, 32, 4, 4, 4, 14502),
    (10, 16, 2, 2, 3, 188),
    (1600, 32, 4, 4, 18, 65261),
])
def test_netdata_disk_space_approximation(disk_count, core_count, interface_count, pool_count, days, expected_output):
    assert calculate_disk_space_for_netdata(get_metrics_approximation(
        disk_count, core_count, interface_count, pool_count
    ), days) == expected_output
